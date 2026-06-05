import psycopg
from enum import Enum
from backend.config import config

class DatabaseConnectionTypes(Enum):
    AIS = 0
    ADSB = 1

def _database_configs(conn_type: DatabaseConnectionTypes) -> dict:
    if config.DB_USING_SQLITE:
        return {
            "path": config.DB_PATH
        }
    else:
        if conn_type == DatabaseConnectionTypes.AIS:
            return {
                "host": config.DB_HOST,
                "dbname": config.AIS_DB_NAME,
                "user": config.DB_USER,
                "password": config.DB_PASS,
                "port": config.DB_PORT,
            }
        elif conn_type == DatabaseConnectionTypes.ADSB:
            return {
                "host": config.DB_HOST,
                "dbname": config.ADSB_DB_NAME,
                "user": config.DB_USER,
                "password": config.DB_PASS,
                "port": config.DB_PORT,
            }
        else:
            raise ValueError(f"Unsupported connection type: {conn_type}")

def get_conn(conn_type: DatabaseConnectionTypes = DatabaseConnectionTypes.AIS):
    db_config = _database_configs(conn_type)

    # Validate required vars
    for key, value in db_config.items():
        if value is None:
            raise ValueError(f"Missing environment variable: {key}")

    try:
        if config.DB_USING_SQLITE:
            import sqlite3
            conn = sqlite3.connect(config.DB_PATH)
            return conn
        conn = psycopg.connect(**db_config)
        return conn
    except psycopg.Error as e:
        raise ConnectionError(f"Failed to connect to database: {e}") from e



######################################### Functions for planes ##########################################

def query_adsb_positions(searchQuery: dict, sort=False):
    conn = get_conn(DatabaseConnectionTypes.ADSB)
    cursor = conn.cursor()

    prompt = "SELECT * FROM adsb_positions WHERE "
    for key, value in searchQuery.items():
        prompt += f"{key} = %s AND "
    prompt = prompt[:-5] + ";"  # Remove trailing ' AND ' and add semicolon
    
    cursor.execute(prompt, tuple(searchQuery.values()))
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


if (__name__ == "__main__"):
    results = query_ais_positions({"MMSI": 368011000})
    print(results)