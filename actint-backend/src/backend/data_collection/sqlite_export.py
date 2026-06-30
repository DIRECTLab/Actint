import json
import sqlite3
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

# ---------------- Configuration ----------------

BATCH_SIZE = 10_000

AIS_REGION_WHERE = (
    '("lat" BETWEEN %s AND %s AND "lon" BETWEEN %s AND %s) '
    'OR ("lat" BETWEEN %s AND %s AND "lon" BETWEEN %s AND %s)'
)

AIS_REGION_PARAMS = (
    32.69987501768122,
    40.17113327771455,
    -126.85274608571916,
    -114.6130282867166,
    15.142852418646005,
    25.239916792977784,
    -163.38317046558294,
    -148.3043921944621,
)

DBS = {
    "AIS": {
        "pg_conninfo": (
            "host=129.123.61.22 port=10543 dbname=actint "
            "user=direct password=spottherobot"
        ),
        "pg_schema": "public",
        "sqlite_path": "output.db",
        "tables": {
            "ais_dynamic_data": {},
            "ais_static_data": {},
            "mmsi_mid_country": {},
            "ship_status": {},
            "vessel_type": {},
        },
    },
    "ADSB": {
        "pg_conninfo": (
            "host=129.123.61.22 port=10543 dbname=postgres "
            "user=direct password=spottherobot"
        ),
        "pg_schema": "public",
        "sqlite_path": "output.db",
        "tables": {
            "airports": {},
            "aircraft": {},
            "avi_countries": {},
            "avi_navaids": {},
            "avi_regions": {},
            "runways": {},
            
            "adsb_positions": {
                "where_clause": (
                    f"({AIS_REGION_WHERE}) "
                    'AND "timestamp" IS NOT NULL '
                    'AND "timestamp" >= ('
                    'SELECT MAX("timestamp") - INTERVAL \'7 days\' '
                    'FROM adsb_positions'
                    ')'
                ),
                "where_params": AIS_REGION_PARAMS,
                "checks": [
                    '"lat" BETWEEN -90 AND 90',
                    '"lon" BETWEEN -180 AND 180',
                ],
            },
        },
    },
}

# -----------------------------------------------

PG_TO_SQLITE: dict[str, str] = {
    "integer": "INTEGER",
    "bigint": "INTEGER",
    "smallint": "INTEGER",
    "serial": "INTEGER",
    "bigserial": "INTEGER",
    "smallserial": "INTEGER",
    "boolean": "INTEGER",
    "real": "REAL",
    "double precision": "REAL",
    "float": "REAL",
    "numeric": "NUMERIC",
    "decimal": "NUMERIC",
    "text": "TEXT",
    "character varying": "TEXT",
    "varchar": "TEXT",
    "char": "TEXT",
    "character": "TEXT",
    "uuid": "TEXT",
    "date": "TEXT",
    "timestamp without time zone": "TEXT",
    "timestamp with time zone": "TEXT",
    "time without time zone": "TEXT",
    "time with time zone": "TEXT",
    "json": "TEXT",
    "jsonb": "TEXT",
    "bytea": "BLOB",
    "inet": "TEXT",
    "cidr": "TEXT",
    "macaddr": "TEXT",
    "interval": "TEXT",
    "array": "TEXT",
}


def map_pg_type(pg_type: str) -> str:
    return PG_TO_SQLITE.get(pg_type.lower(), "TEXT")


def coerce_value(value):
    """Convert Python types that SQLite can't handle natively.

    psycopg3 deserializes PG values into rich Python types. SQLite only
    accepts int, float, str, bytes, and None natively.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, memoryview):
        return bytes(value)
    return value


def get_columns(pg_conn: psycopg.Connection, schema: str, table_name: str) -> list[dict]:
    with pg_conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table_name),
        )
        return cur.fetchall()


def get_primary_keys(
    pg_conn: psycopg.Connection, schema: str, table_name: str
) -> list[str]:
    with pg_conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
               AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
            """,
            (schema, table_name),
        )
        return [row["column_name"] for row in cur.fetchall()]


def build_create_table_sql(
    table_name: str,
    columns: list[dict],
    primary_keys: list[str],
    checks: list[str] | None = None,
) -> str:
    pk_set = set(primary_keys)
    col_defs = []

    for col in columns:
        name = col["column_name"]
        sqlite_type = map_pg_type(col["data_type"])
        not_null = "NOT NULL" if col["is_nullable"] == "NO" else ""
        inline_pk = (
            "PRIMARY KEY" if name in pk_set and len(primary_keys) == 1 else ""
        )

        parts = [f'"{name}"', sqlite_type, inline_pk, not_null]
        col_defs.append("    " + " ".join(p for p in parts if p))

    if len(primary_keys) > 1:
        pk_cols = ", ".join(f'"{k}"' for k in primary_keys)
        col_defs.append(f"    PRIMARY KEY ({pk_cols})")

    for expr in checks or []:
        col_defs.append(f"    CHECK ({expr})")

    return (
        f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n'
        + ",\n".join(col_defs)
        + "\n);"
    )


def build_select_query(
    schema: str,
    table_name: str,
    where_clause: str | None = None,
):
    query = sql.SQL("SELECT * FROM {schema}.{table}").format(
        schema=sql.Identifier(schema),
        table=sql.Identifier(table_name),
    )

    if where_clause:
        query += sql.SQL(" WHERE ") + sql.SQL(where_clause)

    return query


def migrate_table(
    pg_conn: psycopg.Connection,
    sqlite_conn: sqlite3.Connection,
    table_name: str,
    pg_schema: str,
    table_cfg: dict | None = None,
):
    table_cfg = table_cfg or {}
    where_clause = table_cfg.get("where_clause")
    where_params = table_cfg.get("where_params", ())
    checks = table_cfg.get("checks", [])

    print(f"[{table_name}] Fetching schema...")
    columns = get_columns(pg_conn, pg_schema, table_name)
    if not columns:
        print(f"[{table_name}] Not found or has no columns. Skipping.")
        return

    primary_keys = get_primary_keys(pg_conn, pg_schema, table_name)
    create_sql = build_create_table_sql(
        table_name,
        columns,
        primary_keys,
        checks=checks,
    )

    sqlite_conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    sqlite_conn.execute(create_sql)
    sqlite_conn.commit()

    col_names = [col["column_name"] for col in columns]
    placeholders = ", ".join(["?"] * len(col_names))
    col_list = ", ".join(f'"{c}"' for c in col_names)
    insert_sql = (
        f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
    )

    select_query = build_select_query(
        pg_schema,
        table_name,
        where_clause=where_clause,
    )

    total = 0
    with pg_conn.transaction():
        with pg_conn.cursor(name=f"migrate_{table_name}", row_factory=dict_row) as cur:
            cur.execute(select_query, where_params)

            while True:
                rows = cur.fetchmany(BATCH_SIZE)
                if not rows:
                    break

                row_data = [
                    tuple(coerce_value(row[col]) for col in col_names)
                    for row in rows
                ]

                sqlite_conn.executemany(insert_sql, row_data)
                sqlite_conn.commit()

                total += len(rows)
                print(f"[{table_name}] {total} rows inserted...", end="\r")

    print(f"[{table_name}] Done: {total} rows.          ")


def db_to_sqlite(dbname: str):
    cfg = DBS[dbname]

    print("##############################################\n")
    print(f"Connecting to database: {dbname}")

    print("\nINFO:")
    print(f"\tPG_CONNINFO: {cfg['pg_conninfo']}")
    print(f"\tPG_SCHEMA: {cfg['pg_schema']}")
    print(f"\tSQLITE_PATH: {cfg['sqlite_path']}")
    print(f"\tTABLES: {list(cfg['tables'].keys())}")

    print("\n##############################################")

    try:
        with psycopg.connect(cfg["pg_conninfo"], autocommit=True) as pg_conn:
            print(f"Opening SQLite at '{cfg['sqlite_path']}'...")
            sqlite_conn = sqlite3.connect(cfg["sqlite_path"])

            try:
                for table_name, table_cfg in cfg["tables"].items():
                    try:
                        migrate_table(
                            pg_conn=pg_conn,
                            sqlite_conn=sqlite_conn,
                            table_name=table_name,
                            pg_schema=cfg["pg_schema"],
                            table_cfg=table_cfg,
                        )
                    except Exception as e:
                        print(f"[{table_name}] ERROR: {e}")
                        sqlite_conn.rollback()
            finally:
                sqlite_conn.close()
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return

    print("\nMigration complete.")


def ais_to_sqlite():
    db_to_sqlite("AIS")


def adsb_to_sqlite():
    db_to_sqlite("ADSB")


def main():
    ais_to_sqlite()
    adsb_to_sqlite()


if __name__ == "__main__":
    main()