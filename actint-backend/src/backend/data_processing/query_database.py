from datetime import datetime
import os
import psycopg

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH_AIS = DB_DIR / "ais.db"
SQLITE_PATH_ADSB = DB_DIR / "adsb.db"


def get_conn():
    from backend.config import config
    try:
        # Read environment variables
        db_config = {
            "host": config.DB_HOST,
            "dbname": config.AIS_DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASS,
            "port": config.DB_PORT,
        }

        # Validate required vars
        for key, value in db_config.items():
            if value is None:
                raise ValueError(f"Missing environment variable: {key}")

        # Connect
        conn = psycopg.connect(**db_config)
        return conn
        
    except Exception as e:
        print("Error:")
        print(e)



######################################### Functions for planes ##########################################

def query_adsb_positions(searchQuery: dict, sort=False):
    conn = get_conn()
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