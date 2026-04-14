"""
MCP server for the SQL specialist agent.

This server intentionally exposes only database-oriented tools so the SQL
agent is constrained to read-only SQL retrieval tasks.
"""

import json
import os
import sqlite3
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "ais.db"

mcp = FastMCP("AIS SQL Specialist", "1.0.0")


def _resolve_sqlite_path() -> Path:
    """Resolve SQLite path, allowing benchmark overrides via env var."""
    override = os.getenv("ACTINT_SQLITE_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return SQLITE_PATH


def _quote_sqlite_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier (table/column name)."""
    return '"' + (identifier or "").replace('"', '""') + '"'


@mcp.tool()
def get_database_info() -> str:
    """Return schema info for the ais_positions table.

    Returns:
        str: JSON object containing database path and ais_positions column metadata.
    """
    try:
        sqlite_path = _resolve_sqlite_path()
        if not sqlite_path.exists():
            return json.dumps({"error": f"SQLite database not found at {sqlite_path}"})

        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()

        table_name = "ais_positions"
        quoted = _quote_sqlite_identifier(table_name)
        cursor.execute(f"PRAGMA table_info({quoted});")

        columns = []
        for cid, name, col_type, notnull, dflt_value, pk in cursor.fetchall():
            columns.append(
                {
                    "cid": cid,
                    "name": name,
                    "type": col_type,
                    "notnull": bool(notnull),
                    "default": dflt_value,
                    "pk": bool(pk),
                }
            )

        conn.close()

        if not columns:
            return json.dumps({"error": "Table 'ais_positions' not found"})

        return json.dumps(
            {
                "db_path": str(sqlite_path),
                "table_count": 1,
                "tables": [{"name": table_name, "columns": columns}],
            },
            indent=2,
        )
    except sqlite3.Error as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Introspection error: {str(e)}"})


@mcp.tool()
def query_database(sql_query: str, max_rows: int | str = 200) -> str:
    """Execute a read-only SQL query against the AIS database.

    Args:
        sql_query (str): Read-only SQL query to execute (SELECT / WITH ... SELECT).
        max_rows (int): Maximum rows to return (default: 200, capped at 5000).

    Returns:
        str: JSON payload with columns, rows, and truncation metadata.
    """
    try:
        max_rows = int(max_rows)
        query = (sql_query or "").strip()
        if not query:
            return json.dumps({"error": "sql_query is required"})

        ql = query.lower().lstrip()
        if not (ql.startswith("select") or ql.startswith("with")):
            return json.dumps({"error": "Only read-only SELECT queries are allowed"})

        forbidden = [
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "attach ",
            "detach ",
            "vacuum",
            "pragma",
            "reindex",
            "replace ",
            "truncate ",
        ]
        if any(tok in ql for tok in forbidden):
            return json.dumps({"error": "Query contains forbidden keywords"})

        if ";" in query.rstrip(";"):
            return json.dumps({"error": "Multiple SQL statements are not allowed"})

        if max_rows <= 0:
            max_rows = 200
        if max_rows > 5000:
            max_rows = 5000

        conn = sqlite3.connect(str(_resolve_sqlite_path()))
        cursor = conn.cursor()
        cursor.execute(query)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(max_rows + 1)
        conn.close()

        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]

        result_rows = []
        for row in rows:
            result_rows.append({col: val for col, val in zip(columns, row)})

        return json.dumps(
            {
                "columns": columns,
                "row_count": len(result_rows),
                "truncated": truncated,
                "max_rows": max_rows,
                "rows": result_rows,
            },
            indent=2,
        )
    except sqlite3.Error as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Query error: {str(e)}"})


if __name__ == "__main__":
    mcp.run()
