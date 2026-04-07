import sqlite3
from pathlib import Path


def table_summary(cursor, table, time_col="timestamp"):
    print(f"\n=== {table} ===")

    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Total rows: {count}")

    if count == 0:
        return

    cursor.execute(f"""
        SELECT * FROM {table}
        ORDER BY {time_col} ASC
        LIMIT 1
    """)
    print("First row:", cursor.fetchone())

    cursor.execute(f"""
        SELECT * FROM {table}
        ORDER BY {time_col} DESC
        LIMIT 1
    """)
    print("Last row:", cursor.fetchone())


def time_range(cursor):
    cursor.execute("""
        SELECT 
            MIN(timestamp),
            MAX(timestamp),
            (MAX(timestamp) - MIN(timestamp))
        FROM adsb_positions
    """)
    min_ts, max_ts, span = cursor.fetchone()

    print("\n=== Time Coverage ===")
    print(f"Start: {min_ts}")
    print(f"End:   {max_ts}")
    print(f"Span (hrs): {span / 3600 if span else 0:.2f}")
    print(f"Span (days): {span / (3600*24) if span else 0:.2f}")


def aircraft_stats(cursor):
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT icao),
            COUNT(*),
            COUNT(*) * 1.0 / COUNT(DISTINCT icao)
        FROM adsb_positions
    """)
    unique_aircraft, total_rows, avg_points = cursor.fetchone()

    print("\n=== Aircraft Stats ===")
    print(f"Unique aircraft: {unique_aircraft}")
    print(f"Total rows: {total_rows}")
    print(f"Avg points per aircraft: {avg_points:.2f}")


def top_aircraft(cursor, limit=5):
    cursor.execute(f"""
        SELECT icao, COUNT(*) as cnt
        FROM adsb_positions
        GROUP BY icao
        ORDER BY cnt DESC
        LIMIT {limit}
    """)

    print("\n=== Top Aircraft by Messages ===")
    for row in cursor.fetchall():
        print(row)


def null_checks(cursor):
    cursor.execute("""
        SELECT
            SUM(lat IS NULL),
            SUM(lon IS NULL),
            SUM(altitude IS NULL),
            SUM(ground_speed IS NULL),
            SUM(track IS NULL)
        FROM adsb_positions
    """)

    lat_null, lon_null, alt_null, speed_null, track_null = cursor.fetchone()

    print("\n=== Null Counts ===")
    print(f"lat nulls: {lat_null}")
    print(f"lon nulls: {lon_null}")
    print(f"altitude nulls: {alt_null}")
    print(f"speed nulls: {speed_null}")
    print(f"track nulls: {track_null}")


def geo_bounds(cursor):
    cursor.execute("""
        SELECT 
            MIN(lat), MAX(lat),
            MIN(lon), MAX(lon)
        FROM adsb_positions
    """)

    min_lat, max_lat, min_lon, max_lon = cursor.fetchone()

    print("\n=== Geo Bounds ===")
    print(f"Lat: {min_lat} → {max_lat}")
    print(f"Lon: {min_lon} → {max_lon}")


def value_ranges(cursor):
    cursor.execute("""
        SELECT 
            MIN(altitude), MAX(altitude),
            MIN(ground_speed), MAX(ground_speed)
        FROM adsb_positions
    """)

    min_alt, max_alt, min_spd, max_spd = cursor.fetchone()

    print("\n=== Value Ranges ===")
    print(f"Altitude: {min_alt} → {max_alt}")
    print(f"Speed:    {min_spd} → {max_spd}")


def ingestion_rate(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) * 1.0 / ((MAX(timestamp) - MIN(timestamp)) / 60.0)
        FROM adsb_positions
        WHERE timestamp IS NOT NULL
    """)

    rate = cursor.fetchone()[0]

    print("\n=== Ingestion Rate ===")
    print(f"Messages per minute: {rate:.2f}")


def aircraft_table_check(cursor):
    cursor.execute("SELECT COUNT(*) FROM aircraft")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT icao) FROM adsb_positions")
    distinct_positions = cursor.fetchone()[0]

    print("\n=== Aircraft Table Check ===")
    print(f"Aircraft table rows: {total}")
    print(f"Distinct ICAO in positions: {distinct_positions}")


DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = DATA_DIR / "processed"
BATCH_SIZE = 5000

# Paths
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "adsb.db"
CHROMA_PATH = DB_DIR / "adsb_chroma"



def main():
    # change this to your DB path
    db_path = SQLITE_PATH

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n===== DATABASE HEALTH CHECK =====")

    # Core structure checks
    table_summary(cursor, "adsb_positions", "timestamp")
    table_summary(cursor, "aircraft", "last_seen")

    # Coverage + density
    time_range(cursor)
    aircraft_stats(cursor)
    ingestion_rate(cursor)

    # Data quality
    null_checks(cursor)
    geo_bounds(cursor)
    value_ranges(cursor)

    # Behavioral insight
    top_aircraft(cursor)

    # Consistency
    aircraft_table_check(cursor)

    conn.close()


if __name__ == "__main__":
    main()