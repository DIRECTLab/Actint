"""
Usage: run this script with date arguments to get ADS-B json data for a give day or range of days

Example:    python3 data_collector.py --start 3/5/25 --end 3/10/26
            python3 data_collector.py --start 3/5/25                                 //just gets data for start date
            python3 data_collector.py --start 3/5/25 --end 3/10/26 --vehicles 50     //gets data for the first 50 vehicles found in day one for the whole time range

Optional arguments: data-out-dir (set output directory to store json data in) defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
"""

import argparse
import requests
import tarfile
import gzip
import json
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta 
from contextlib import nullcontext
import io
from alive_progress import alive_bar
import re
import gc
import os
import psycopg

# Paths

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = DATA_DIR / "processed"

DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "adsb.db"

BASE_URL = "https://github.com/adsblol/globe_history_{year}/releases/download"


# Argument parsing

def parse_args():
    parser = argparse.ArgumentParser(description="ADS-B Data Collector")
    parser.add_argument("--start", required=True, help="Start date MM/DD/YY")
    parser.add_argument("--end", help="End date MM/DD/YY (optional)")
    parser.add_argument("--data-out-dir", type=Path, default=OUT_DIR, help="Output directory for processed data")
    parser.add_argument("--db-file", type=Path, default=DATA_DIR / "adsb.sqlite", help="Output file for SQLite DB")
    parser.add_argument("--vehicles", help="Integer value to only capture first n vessels' data (optional)")
    return parser.parse_args()


# Date range

def build_date_range(day_delta, start_str, end_str=None):
    start = datetime.strptime(start_str, "%m/%d/%y")
    end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start
    current = start
    days = []
    while current <= end:
        days.append(current)
        current += timedelta(days=day_delta)
    return days


# Downloading TAR to memory

def process_full_day(day,year): 
    
    tar_buffer = download_Tar_File(day, year)

    if not tar_buffer:
        print(f"Tar_buffer empty, skipping day")
        return

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
        
        #tar.extractall(RAW_DIR, filter=lambda tarinfo, _: tarinfo) #writes extracted tar to raw data directory (need to add date folder)
        total_matches = 0

        for member in tar.getmembers():
            if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                total_matches = total_matches + 1
            
        #print(f"Total JSON Matches: {total_matches}")

        with alive_bar(total_matches) as bar:

            bar.title = 'Ingesting ADS-B JSON -> SQL'

            conn = get_conn()

            for member in tar.getmembers():

                bar.text(f"File: {member.name[-11:]}")

                # Match files in traces/00-ff/ ending in .json
                if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name): #all json matched
                    f = tar.extractfile(member)
                    if f:
                        with gzip.open(f, 'rt', encoding='utf-8') as gz:
                            try:
                                data = json.load(gz)
                                normed_data = normalize_data([data])

                                insert_to_sqlite(conn, normed_data)

                                #all_records.append(normed_data)
                            except (json.JSONDecodeError, gzip.BadGzipFile):
                                continue

                            #clean up unused objects now that all data is saved 
                            del data
                            del gz
                            del f
                            gc.collect()
                            bar() #increments the alive progress bar


# Downloading TAR to memory and extract fixed vehicle list

def process_vehicle_list(day, year, vehicle_list): 

    tar_buffer = download_Tar_File(day, year)

    if not tar_buffer:
        print(f"Tar_buffer empty, skipping day")
        return

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:

        with alive_bar(len(vehicle_list)) as bar:

            bar.title = 'Ingesting ADS-B JSON -> SQL'

            conn = get_conn()

            for member in vehicle_list:

                bar.text(f"File: {member[-11:]}")

                try:
                    f = tar.extractfile(member)
                    if f:
                        with gzip.open(f, 'rt', encoding='utf-8') as gz:
                            try:
                                data = json.load(gz)
                                normed_data = normalize_data([data])

                                insert_to_sqlite(conn, normed_data)

                                #all_records.append(normed_data)
                            except (json.JSONDecodeError, gzip.BadGzipFile):
                                continue

                            #clean up unused objects now that all data is saved 
                            del data
                            del gz
                            del f
                            gc.collect()
                            bar() #increments the alive progress bar
                except:
                    continue


# Normalize JSON data (flatten and map added keys)

def normalize_data(json_data):

    flattened = []

    for record in json_data:

        base = {
            "ICAO": record.get("icao"),
            "REG_NUM": record.get("r") if record.get("r") else f"noRegData: {record.get("noRegData")}"  ,
            "TYPE": record.get("t"),
            "DESC": record.get("desc"),
            "DBFLAGS": record.get("dbFlags"),
            "MILITARY": bool(record.get("dbFlags", 0) & 1),
            #"interesting": bool(record.get("dbFlags", 0) & 2),
            #"pia": bool(record.get("dbFlags", 0) & 4),
            #"ladd": bool(record.get("dbFlags", 0) & 8),
            #"TIMESTAMP": record.get("timestamp"),
        }

        TIMESTAMP = record.get("timestamp")

        trace_list = record.get("trace", [])

        for entry in trace_list:
            if not isinstance(entry, list):
                continue

            meta = entry[8] if len(entry) > 8 and isinstance(entry[8], dict) else {}
            
            # unpack with safe indexing
            trace_obj = {
                **base,
                #"TIME_OFFSET": entry[0] if len(entry) > 0 else None,
                "TIMESTAMP": TIMESTAMP + (entry[0] if len(entry) > 0 else None),
                "LAT": entry[1] if len(entry) > 1 else None,
                "LON": entry[2] if len(entry) > 2 else None,
                "ALTITUDE": entry[3] if len(entry) > 3 else None,
                "GROUND_SPEED": entry[4] if len(entry) > 4 else None,
                "TRACK": entry[5] if len(entry) > 5 else None,
                "FLAGS": entry[6] if len(entry) > 6 else None,
                "VERTICAL_RATE": entry[7] if len(entry) > 7 else None,
                
                # ===== ADS-B METADATA entry[8] =====
                "FLIGHT_NUMBER": meta.get("flight"),
                "EMERGENCY": meta.get("emergency"),
                "CATEGORY": meta.get("category"),
                "RC_METERS": meta.get("rc"),

                "POS_SOURCE": entry[9] if len(entry) > 9 else None,
                "ALT_GEOM": entry[10] if len(entry) > 10 else None,
                "GEOM_RATE": entry[11] if len(entry) > 11 else None,
                "IAS": entry[12] if len(entry) > 12 else None,
                "ROLL": entry[13] if len(entry) > 13 else None,

            }

            # optional: decode flags
            flags = trace_obj["FLAGS"]
            if isinstance(flags, int):
                trace_obj["FLAG_POS_STALE"] = bool(flags & 1)
                trace_obj["FLAG_NEW_LEG"] = bool(flags & 2)
                trace_obj["FLAG_GEOM_RATE"] = bool(flags & 4)
                trace_obj["FLAG_GEOM_ALT"] = bool(flags & 8)
        
            #remove ground text on altitude and change to 0
            if trace_obj["ALTITUDE"] == "ground":
                trace_obj["ALTITUDE"] = 0

            flattened.append(trace_obj)

    return flattened


#Creates the AIS position and aircraft tables

def create_sql_schema(conn):
    """Create SQL tables for ADS-B data."""
    cursor = conn.cursor()
    
    # Main AIS positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adsb_positions (
            id BIGSERIAL,
            icao TEXT NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            altitude INTEGER,
            ground_speed REAL,
            track REAL,
            flags INTEGER,                
            vertical_rate INTEGER,
            flight_number TEXT,
            emergency TEXT,
            category TEXT,
            rc_meters INTEGER,
            pos_source TEXT,
            alt_geom INTEGER,
            geom_rate INTEGER,
            ias TEXT,
            roll TEXT,
            flag_pos_stale BOOLEAN,
            flag_new_leg BOOLEAN,
            flag_geom_rate BOOLEAN,
            flag_geom_alt BOOLEAN,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                   
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
    """)

    #removed
    
    #reg_num TEXT NOT NULL,
    #type TEXT,
    #desc TEXT,
    #db_flags INTEGER,
    #military BOOLEAN, 
    
    # Aircraft metadata table (static info, normalized)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aircraft (
            
            icao TEXT PRIMARY KEY,
            reg_num TEXT,
            type TEXT,
            description TEXT,
            db_flags INTEGER,
            military BOOLEAN, 
            first_seen TIMESTAMPTZ,
            last_seen TIMESTAMPTZ   
        )
    """)
    
    
    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_icao ON adsb_positions(icao)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_datetime ON adsb_positions(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_coords ON adsb_positions(lat, lon, altitude)")

    
    conn.commit()
    print("SQLite schema created\n")



#Create monthly partitions for adsb_positions and a DEFAULT partition for stragglers.

def create_monthly_partitions(conn, start_str, end_str=None):

    cur = conn.cursor()

    # parse inputs (fixed bug: no variable shadowing)
    start = datetime.strptime(start_str, "%m/%d/%y")
    end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start

    # normalize to month boundaries
    current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_boundary = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # create monthly partitions
    while current < end_boundary:
        next_month = current + relativedelta(months=1)

        table_name = f"adsb_positions_{current.strftime('%Y_%m')}"
        start_bound = current.strftime('%Y-%m-%d')
        end_bound = next_month.strftime('%Y-%m-%d')

        query = f"""
        CREATE TABLE IF NOT EXISTS {table_name}
        PARTITION OF adsb_positions
        FOR VALUES FROM ('{start_bound}') TO ('{end_bound}');
        """

        cur.execute(query)

        current = next_month

    # DEFAULT partition (catch-all)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS adsb_positions_default
        PARTITION OF adsb_positions
        DEFAULT;
    """)

    conn.commit()


#inserts data into the sql DB 

def insert_to_sqlite(conn, data: list[dict]) -> None:
    """Insert normalized data into SQLite."""
    cursor = conn.cursor()
    
    # Track vessels for metadata table
    vessels_seen = {}
    
    #print("Inserting ADS-B positions...")
    for i, record in enumerate(data):
        # Insert position
        cursor.execute("""
            INSERT INTO adsb_positions (
                    
                icao,  
                timestamp, lat, lon, altitude, ground_speed, 
                track, flags, vertical_rate, flight_number,
                emergency, category, rc_meters, pos_source, alt_geom, 
                geom_rate, ias, roll, flag_pos_stale, flag_new_leg,  
                flag_geom_rate, flag_geom_alt 

            ) VALUES (%s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            record.get("ICAO"),
            #record.get("REG_NUM"),
            #record.get("TYPE"),
            #record.get("DESC"),
            #record.get("DBFLAGS"),
            #record.get("MILITARY"),
            record.get("TIMESTAMP"),
            record.get("LAT"),
            record.get("LON"),
            record.get("ALTITUDE"),
            record.get("GROUND_SPEED"),
            record.get("TRACK"),
            record.get("FLAGS"),
            record.get("VERTICAL_RATE"),
            record.get("FLIGHT_NUMBER"),
            record.get("EMERGENCY"),
            record.get("CATEGORY"),
            record.get("RC_METERS"),
            record.get("POS_SOURCE"),
            record.get("ALT_GEOM"),
            record.get("GEOM_RATE"),
            record.get("IAS"),
            record.get("ROLL"),
            record.get("FLAG_POS_STALE"),
            record.get("FLAG_NEW_LEG"),
            record.get("FLAG_GEOM_RATE"),
            record.get("FLAG_GEOM_ALT"),
        ))
        
        # Track vessel metadata
        icao = record.get("ICAO")
        if icao:
            dt = record.get("TIMESTAMP", "")
            if icao not in vessels_seen:
                vessels_seen[icao] = {

                    "icao": icao,
                    "reg_num": record.get("REG_NUM"),
                    "type": record.get("TYPE"),
                    "description": record.get("DESC"),
                    "db_flags": record.get("DBFLAGS"),
                    "military": record.get("MILITARY"),
                    "first_seen": dt,
                    "last_seen": dt,
                }
            else:
                # Update last_seen
                if dt > vessels_seen[icao]["last_seen"]:
                    vessels_seen[icao]["last_seen"] = dt
        
        
        if (i + 1) % 50000 == 0:
            print(f"  Processed {i + 1}/{len(data)} records...")
            conn.commit()
    
    conn.commit()
    #print(f"Inserted {len(data)} position records")   

    # Insert vessel metadata
    #print("Inserting vessel metadata...")
    for vessel in vessels_seen.values():
        cursor.execute("""
            INSERT INTO aircraft (
                icao,
                reg_num,
                type,
                description,
                db_flags,
                military, 
                first_seen,
                last_seen 
            ) VALUES (
                %s, %s, %s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s)
            )
            ON CONFLICT (icao) DO UPDATE SET
                reg_num = EXCLUDED.reg_num,
                type = EXCLUDED.type,
                description = EXCLUDED.description,
                db_flags = EXCLUDED.db_flags,
                military = EXCLUDED.military,
                first_seen = LEAST(aircraft.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(aircraft.last_seen, EXCLUDED.last_seen)
        """, (
            vessel["icao"],
            vessel["reg_num"],
            vessel["type"],
            vessel["description"],
            vessel["db_flags"],
            vessel["military"],
            vessel["first_seen"],
            vessel["last_seen"],
        ))
    
    conn.commit()
    #print(f"Inserted {len(vessels_seen)} vessel records")
    

def get_check_range(start, end):

    start_date = datetime.strptime(start, "%m/%d/%y")
    end_date = datetime.strptime(end, "%m/%d/%y") if end else start_date

    #do up to 5 checks then add checks for gaps of more than 28 days
    #examples - 4 days do 4 checks, 10 days do 5 checks, 360 days do 12 checks
    
    date_range_delta = (end_date - start_date).days + 1

    if date_range_delta <= 5:
        check_days = build_date_range(1, start, end)

    elif date_range_delta/5 <= 28:
        check_delta = date_range_delta/5
        check_days = build_date_range(check_delta, start, end)

    else: #check days have more that 28 days between them
        check_days = build_date_range(28, start, end)

    #print(f"date range: {date_range_delta}")
    #print(f"check_days: {check_days}")
    #print(f"check days count: {len(check_days)}")

    return check_days


def get_valid_vehicles(check_dates, vehicle_count):
    
    all_vehicles = []
    vehicles_to_use = []

    #get all members for all check days
    with alive_bar(len(check_dates), title=f"Spot-checking Vehicle Continuity:") as bar:
        for i, day in enumerate(check_dates):
            
            bar.text(f"Processing {day:%Y.%m.%d}")

            all_vehicles.append([]) #create the sublist for the day

            #download the tar file
            tar_buffer = download_Tar_File(day, day.year, show_bar=False)
            
            #save all tar members to an array 
            with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
            
                total_matches = 0

                for member in tar.getmembers():
                    if re.match(r'^./traces/[0-9a-fA-F]{2}/trace_full_[0-9a-fA-F]{6}.json$', member.name):
                        total_matches = total_matches + 1
                        all_vehicles[i].append(member.name)
                    
                print(f"{day:%Y.%m.%d} Total Vehicles = {total_matches}")
            bar()

    #pick the first n of them that appear in all days
    index = 0 #candidate index in day 0
    while len(vehicles_to_use) < vehicle_count:

        while index < len(all_vehicles[0]):
            candidate = all_vehicles[0][index]
            match_found = True

            # check if candidate exists in every day
            for vehicle_day in all_vehicles:
                if candidate not in vehicle_day:
                    match_found = False
                    break

            if match_found:
                vehicles_to_use.append(candidate)
                index += 1
                break  # move on to next vehicle

            index += 1
    
    return vehicles_to_use

    #do we want to check for nulls? pros: cleaner data, more consist  cons: doesn't reflect actual data we will get
    #for now I say no 


def download_Tar_File(day, year, iterations=0, show_bar=True):
    
    if iterations >= 2:
        print("No data found")
        return

    # Define possible tag suffixes to try
    tag_variants = [
        "-0",
        "-0tmp",
    ]

    base_tag = f"v{day:%Y.%m.%d}-planes-readsb-prod"

    bar_context = alive_bar(title=f"Downloading: {day:%Y.%m.%d}") if show_bar else nullcontext()

    with bar_context as bar:
        for suffix in tag_variants:
            tag = f"{base_tag}{suffix}"
            url = f"{BASE_URL.format(year=year)}/{tag}/{tag}.tar"

            parts = []

            try:
                # Try multipart first (.aa, .ab, ...)
                response = requests.get(f"{url}.aa")

                if response.status_code == 200:
                    parts.append(response.content)

                    for b in "bcdefghijklmnopqrstuvwxyz":
                        part = f"a{b}"
                        url_parts = f"{url}.{part}"

                        r = requests.get(url_parts)
                        if r.status_code == 404:
                            break

                        r.raise_for_status()
                        parts.append(r.content)

                else:
                    # Fallback to single tar
                    r = requests.get(url)
                    if r.status_code != 200:
                        continue  # Try next tag variant

                    parts.append(r.content)

                # Success path
                if parts:
                    if show_bar:
                        bar()

                    tar_bytes = b"".join(parts)
                    return io.BytesIO(tar_bytes)

            except requests.exceptions.RequestException:
                continue  # Try next variant

    # If all tag variants fail, recurse to next year
    print("No data found for this year, trying next year")
    return download_Tar_File(day, year + 1, iterations + 1, show_bar)



def add_aircraft_foreign_key(conn) -> None:
    """
    Adds FK constraint adsb_positions(icao) → aircraft(icao) in PostgreSQL.
    Safely skips creation if constraint already exists.
    """

    cursor = conn.cursor()

    try:
        # 1. Check for orphan ICAOs
        cursor.execute("""
            SELECT COUNT(*)
            FROM adsb_positions p
            LEFT JOIN aircraft a ON p.icao = a.icao
            WHERE a.icao IS NULL
              AND p.icao IS NOT NULL
        """)

        missing = cursor.fetchone()[0]

        if missing > 0:
            raise ValueError(
                f"FK blocked: {missing} adsb_positions rows "
                f"do not exist in aircraft table."
            )

        # 2. Check if constraint already exists (Postgres catalog lookup)
        cursor.execute("""
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_adsb_positions_aircraft'
              AND table_name = 'adsb_positions'
        """)

        exists = cursor.fetchone()

        if exists:
            print("Foreign key constraint already exists. Skipping.")
            conn.commit()
            return

        # 3. Add foreign key constraint
        cursor.execute("""
            ALTER TABLE adsb_positions
            ADD CONSTRAINT fk_adsb_positions_aircraft
            FOREIGN KEY (icao)
            REFERENCES aircraft(icao)
        """)

        conn.commit()
        print("Foreign key constraint successfully added.")

    except Exception as e:
        conn.rollback()
        print("Error while adding foreign key:")
        print(e)
        raise

    finally:
        cursor.close()


def drop_aircraft_foreign_key(conn) -> None:
    """
    Drops FK constraint adsb_positions(icao) → aircraft(icao)
    if it exists (PostgreSQL safe).
    """

    cursor = conn.cursor()

    try:
        # Check if constraint exists
        cursor.execute("""
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE c.conname = 'fk_adsb_positions_aircraft'
              AND t.relname = 'adsb_positions'
        """)

        exists = cursor.fetchone()

        if not exists:
            print("\nForeign key constraint does not exist. Nothing to drop.")
            return

        # Drop constraint
        cursor.execute("""
            ALTER TABLE adsb_positions
            DROP CONSTRAINT fk_adsb_positions_aircraft
        """)

        conn.commit()
        print("\nForeign key constraint dropped successfully.")

    except Exception as e:
        conn.rollback()
        print("\nError while dropping foreign key constraint:")
        print(e)
        raise

    finally:
        cursor.close()


def get_conn():
    try:
        # Read environment variables
        db_config = {
            "host": os.getenv("DB_HOST"),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASS"),
            "port": int(os.getenv("DB_PORT")),
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




# Main

def main():
    args = parse_args()
    days = build_date_range(1, args.start, args.end)
    vehicle_count = int(args.vehicles) if args.vehicles else False

    #DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_conn()

    drop_aircraft_foreign_key(conn)
    create_sql_schema(conn)
    create_monthly_partitions(conn, args.start, args.end)

    
    if(vehicle_count):

        #data checking for vehicles 
        check_range = get_check_range(args.start, args.end)
        #print(f"check_days: {check_range}")
        #print(f"check days count: {len(check_range)}")

        vehicle_list = get_valid_vehicles(check_range, vehicle_count)
        #print(f"valid vehicles: {vehicle_list}")

        for day in days:
            print(f"\n[DATE] {day.date()}")
            process_vehicle_list(day, day.year, vehicle_list)
            
    else:
 
        for day in days:
            print(f"\n[DATE] {day.date()}")
            process_full_day(day, day.year)

    add_aircraft_foreign_key(conn)


if __name__ == "__main__":
    main()