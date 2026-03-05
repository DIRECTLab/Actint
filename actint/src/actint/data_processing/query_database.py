import sqlite3 

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "ais.db"

def _get_sqlite_connection() -> sqlite3.Connection:
    """Get a SQLite connection."""
    return sqlite3.connect(SQLITE_PATH)

def query_ais_positions(searchQuery: dict):
    conn = _get_sqlite_connection()
    cursor = conn.cursor()
    for key, value in searchQuery.items():
        cursor.execute(f"SELECT * FROM ais_positions WHERE {key} = ?", (value,))
    results = cursor.fetchall()
    conn.close()
    return results



def query_fleets(searchQuery: dict):
    conn = _get_sqlite_connection()
    cursor = conn.cursor()
    for key, value in searchQuery.items():
        cursor.execute(f"SELECT * FROM fleets WHERE {key} = ?", (value,))
    results = cursor.fetchall()
    conn.close()
    return results



def query_vessels(searchQuery: dict):
    conn = _get_sqlite_connection()
    cursor = conn.cursor()
    for key, value in searchQuery.items():
        cursor.execute(f"SELECT * FROM vessels WHERE {key} = ?", (value,))
    results = cursor.fetchall()
    conn.close()
    return results