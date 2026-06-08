#general idea
"""
create all the basic sql queries we will need to use here that can be built upon later for more complex tooling
basic tools includes
    get conn() -> connection to postgres db
    select_one() used to look up a value that only has one match
    icao to reg (icao)
    reg to country iso (reg)
    country iso to name (iso)

    get last location (icao)
    get last seen time (icao)

    get vehicle context (icao) -> vehicle type, description and decoded dbflags
    get flight numbers (icao) -> dict of flight numbers, time stamp
    
    
"""

import os
from backend.config import config
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

import math
from typing import Any, Iterable, Optional

from backend.data_processing.query_database import DatabaseConnectionTypes, get_conn


def normalize_icao(icao: str) -> str:
    """Normalize ICAO hex strings for consistent DB lookup."""
    return (icao or "").strip().lower()


def bearing_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def bbox_from_radius_nm(lat: float, lon: float, radius_nm: float) -> tuple[float, float, float, float]:
    """Approximate lat/lon bounding box for a radius in nautical miles."""
    if radius_nm <= 0:
        return lat, lat, lon, lon

    # 1 degree latitude ~= 60 nm
    dlat = radius_nm / 60.0
    # 1 degree longitude ~= 60 nm * cos(latitude)
    denom = 60.0 * max(math.cos(math.radians(lat)), 1e-6)
    dlon = radius_nm / denom
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon

def select_one(conn, table, select_col, where_col, where_val):

    query = sql.SQL("""
        SELECT {select_col}
        FROM {table}
        WHERE {where_col} = %s
        LIMIT 1;
    """).format(
        select_col=sql.Identifier(select_col),
        table=sql.Identifier(table),
        where_col=sql.Identifier(where_col),
    )

    with conn.cursor() as cur:
        cur.execute(query, (where_val,))
        row = cur.fetchone()

    return row[0] if row else None


def select_one_row(
    conn,
    table: str,
    columns: list[str],
    where_col: str,
    where_val: Any,
) -> Optional[dict[str, Any]]:
    """Select a single row and return as a dict keyed by column names."""
    query = sql.SQL("""
        SELECT {columns}
        FROM {table}
        WHERE {where_col} = %s
        LIMIT 1;
    """).format(
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        table=sql.Identifier(table),
        where_col=sql.Identifier(where_col),
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (where_val,))
        row = cur.fetchone()
    return dict(row) if row else None


def select_many_rows(
    conn,
    table: str,
    columns: list[str],
    where: Optional[dict[str, Any]] = None,
    *,
    order_by: Optional[str] = None,
    desc: bool = True,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Select multiple rows and return list[dict]."""
    if limit <= 0:
        limit = 200
    if limit > 5000:
        limit = 5000

    where = where or {}
    where_sql = sql.SQL("TRUE")
    params: list[Any] = []
    if where:
        parts = []
        for key, val in where.items():
            parts.append(sql.SQL("{col} = %s").format(col=sql.Identifier(key)))
            params.append(val)
        where_sql = sql.SQL(" AND ").join(parts)

    order_sql = sql.SQL("")
    if order_by:
        order_sql = sql.SQL(" ORDER BY {col} {direction}").format(
            col=sql.Identifier(order_by),
            direction=sql.SQL("DESC" if desc else "ASC"),
        )

    query = sql.SQL("SELECT {columns} FROM {table} WHERE {where}").format(
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        table=sql.Identifier(table),
        where=where_sql,
    ) + order_sql + sql.SQL(" LIMIT %s")
    params.append(limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]



def icao_to_reg(conn, icao):

    return select_one(conn, 'aircraft', 'reg_num', 'icao', normalize_icao(icao))
  


def reg_to_country_iso(conn, reg):
    
    query = """
        SELECT prefix, iso_country, notes
        FROM reg_num_to_country_iso
        WHERE %s LIKE prefix || '%%'
        ORDER BY LENGTH(prefix) DESC
        LIMIT 1;
    """

    with conn.cursor() as cur:
        cur.execute(query, (reg,))
        row = cur.fetchone()
    return row[1] if row else None



def country_iso_to_name(conn, iso):

    return select_one(conn, 'avi_countries', 'name', 'code', iso)



def get_last_location(conn, icao: str, lookback_months: int = 6):
    """Return the most recent position row for an aircraft."""
    query = """
        SELECT *
        FROM adsb_positions
        WHERE icao = %s
          AND timestamp >= NOW() - make_interval(months => %s)
        ORDER BY timestamp DESC
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(query, (normalize_icao(icao), lookback_months))
        row = cur.fetchone()
    return row


def get_last_seen_time(conn, icao):

    return select_one(conn, 'aircraft', 'last_seen', 'icao', normalize_icao(icao))


def execute_readonly_query(conn, sql_query: str, params: Iterable[Any] = (), max_rows: int = 200) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return rows as dicts.

    Guardrails: SELECT/WITH only, single statement.
    """
    query = (sql_query or "").strip()
    if not query:
        raise ValueError("sql_query is required")

    ql = query.lower().lstrip()
    if not (ql.startswith("select") or ql.startswith("with")):
        raise ValueError("Only read-only SELECT/WITH queries are allowed")

    forbidden = [
        "insert ", "update ", "delete ", "drop ", "alter ", "create ",
        "truncate ", "grant ", "revoke ", "vacuum", "analyze", "refresh ",
        "set ", "call ", "do ",
    ]
    if any(tok in ql for tok in forbidden):
        raise ValueError("Query contains forbidden keywords")

    # crude multi-statement guard
    if ";" in query.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    if max_rows <= 0:
        max_rows = 200
    if max_rows > 5000:
        max_rows = 5000

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchmany(max_rows)
    return [dict(r) for r in rows]


def list_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name;"
        )
        return [r[0] for r in cur.fetchall()]


def describe_table(conn, table_name: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT ordinal_position, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table_name,),
        )
        return [dict(r) for r in cur.fetchall()]


def count_rows(conn, table_name: str) -> int:
    q = sql.SQL("SELECT COUNT(*) FROM {t};").format(t=sql.Identifier(table_name))
    with conn.cursor() as cur:
        cur.execute(q)
        return int(cur.fetchone()[0])
