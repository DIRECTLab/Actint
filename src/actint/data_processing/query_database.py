import sqlite3 
from datetime import datetime
import os

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH_SHIPS = DB_DIR / "ais.db"
SQLITE_PATH_PLANES = DB_DIR / "adsb.db"


def _resolve_sqlite_path() -> Path:
    """Resolve SQLite path, allowing benchmark overrides via env var."""
    override = os.getenv("ACTINT_SQLITE_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return SQLITE_PATH_SHIPS

def _get_sqlite_connection() -> sqlite3.Connection:
    """Get a SQLite connection."""
    return sqlite3.connect(_resolve_sqlite_path())


def _resolve_sqlite_path_asdb() -> Path:
    """Resolve SQLite path, allowing benchmark overrides via env var."""
    override = os.getenv("ACTINT_SQLITE_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return SQLITE_PATH_PLANES



def _get_sqlite_connection_asdb() -> sqlite3.Connection:
    """Get a SQLite connection."""
    return sqlite3.connect(_resolve_sqlite_path_asdb())




###################################### Functions for ships/boats #######################################

def query_ais_positions(searchQuery: dict, sort=False):
    conn = _get_sqlite_connection()
    cursor = conn.cursor()
    for key, value in searchQuery.items():
        cursor.execute(f"SELECT * FROM ais_positions WHERE {key} = ?", (value,))
    results = cursor.fetchall()
    print(results[0][2])
    conn.close()
    if(results and sort):
        sorted_vessels = sorted(
            results,
            key=lambda x: datetime.strptime(x[2], "%Y-%m-%dT%H:%M:%S.%f"),
            reverse=True
        )
        return sorted_vessels
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





######################################### Functions for planes ##########################################


def query_adsb_positions(searchQuery: dict, sort=False):
    conn = _get_sqlite_connection_asdb()
    cursor = conn.cursor()
    for key, value in searchQuery.items():
        cursor.execute(f"SELECT * FROM adsb_positions WHERE {key} = ?", (value,))
    results = cursor.fetchall()
    conn.close()
    if results and sort:
        sorted_planes = sorted(
            results,
            key=lambda x: float(x[7]),
            reverse=True
        )
        return sorted_planes

    return results


