"""
Follow each aircrafts day of data individually, add traversal counts to heatmap bins, track transitions from bin to bin and record transition count, also track and record stats of the craft for each transition 
| `segment_id` | FK → route_segments | |
| `aircraft_type` | string | |
| `ave_gnd_speed` | float | |
| `altitude_band` | float | Use FL avi designation |
| `ave_vert_rate` | float | |
| `ave_ias` | float | indicated air speed |

psuedocode

For each day 
    for each aircraft
        download_day()
        normalize_data()
        determine_route()

determine_route(normed_data):
    
    for entry in normed_data
    

        if altitude <= 1000 ft: #ignore airport ground traffic
            continue

        if(prev_time):
            dt = cur_time - prev_time

        if dt <= 0:
            continue
            
        bin = get_h3_bin(lat,lon)
            
        if (dt <= 5 sec) and (h3_distance(prev_bin, bin) == 1) (reduce bouncing between cells)
            continue 
        
            
        implied speed = haversine(points)/dt
            
        if implied_speed > MAX_SPEED: # 800 knots, check for impossible transition, skip creating the edge segment and move on
            prevbin and point = None
            continue
        

        if bin == previous_bin 
            
            if message["gnd_speed"] not NULL:
                cur_bin_gnd_speed_sum += message["gnd_speed"]
                cur_bin_gnd_speed_count += 1
            "" (duplicate for each summary stat)

            continue
            
        else
            new_bin_traversal += 1 
            record transition
            record_transition_stats(prev_bin, cur_bin)
            prev_bin = cur_bin

record_transition_stats(prev_bin, cur_bin):
    sum prev and cur bin sums and counts
    divide by counts
    find heading variance from average heading in degrees
    record in DB

"""


from datetime import datetime, timedelta
from alive_progress import alive_bar
import tarfile
import gzip
import json
from pathlib import Path

from h3 import cell_to_latlng, latlng_to_cell
from backend.mcp_servers.adsb.helpers.adsb_locations import bbox_from_radius_nm, get_conn
from backend.mcp_servers.adsb.helpers.airport_tools import find_nearest_airport
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm

from contextlib import nullcontext
import re
import requests
import io
import gc
import psycopg

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"

BASE_URL = "https://github.com/adsblol/globe_history_{year}/releases/download"
RES = 7
MAX_SPEED = 2000


def build_date_range(day_delta, start_str, end_str=None):

    start = datetime.strptime(start_str, "%m/%d/%y")
    end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start
    current = start
    days = []
    while current <= end:
        days.append(current)
        current += timedelta(days=day_delta)
    return days


def create_tables(conn):

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS heatmap_bins (
        
                h3_index BIGINT PRIMARY KEY,
                lat_center DOUBLE PRECISION,
                lon_center DOUBLE PRECISION,
                traversal_count BIGINT NOT NULL,
                contains_airport BOOLEAN
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_segments (
        
                id BIGINT PRIMARY KEY,
                start_bin BIGINT,
                end_bin BIGINT,
                transition_count BIGINT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS segment_stats (
        
                segment_id BIGINT PRIMARY KEY,
                aircraft_type TEXT,
                altitude_band TEXT,
                ave_gnd_speed REAL,
                ave_ias REAL,
                ave_vert_rate REAL,
                ave_heading REAL,
                heading_variance REAL
            )
        """)

    conn.commit()


def get_aircraft_count(tar_buffer):

    #with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
    with tarfile.open(tar_buffer, mode="r:*") as tar:

        total_matches = 0

        for member in tar.getmembers():
            if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                
                total_matches = total_matches + 1

    return total_matches



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



def iter_aircrafts_from_tar(tar_path: Path):
    """
    Yields one aircraft JSON object at a time from a tar.gz archive.
    Memory efficient: streams per member.
    """

    pattern = re.compile(r'^./traces/[0-9a-fA-F]{2}/.*\.json$')

    #with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
    with tarfile.open(tar_path, mode="r:*") as tar:

        for member in tar:

            if not pattern.match(member.name):
                continue

            f = tar.extractfile(member)
            if f is None:
                continue

            try:
                with gzip.open(f, "rt", encoding="utf-8") as gz:
                    yield member, json.load(gz)

            except (json.JSONDecodeError, gzip.BadGzipFile):
                continue



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


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def determine_routes(conn, data, airport_cells):

    if not data:
        print(f"no flight data")
        return
    
    prev_time = None
    cur_time = None
    prev_bin = None
    cur_bin = None
    prev_point = None
    cur_point = None
    dt = 10
    implied_speed = 0

    gnd_speed_sum = 0
    alt_sum = 0
    vert_rate_sum = 0
    ias_sum = 0
    heading_sum = 0

    gnd_speed_count = 0
    alt_count = 0
    vert_rate_count = 0
    ias_count = 0
    heading_count = 0

    for entry in data:

        if entry.get("ALTITUDE") == None or entry.get("ALTITUDE") <= 1000:
            #print(f'altitude below threshold: {entry.get("ALTITUDE")}')
            continue 

        cur_time = entry.get("TIMESTAMP")
        #print(f"cur_time: {cur_time}")

        if(prev_time):
            dt = cur_time - prev_time

        #print(f'time delta: {dt}')

        if dt <= 0:
            print(f'negative time delta: {dt}')
            continue

        lat = entry.get("LAT")
        lon = entry.get("LON")

        cur_point = lat, lon

        cur_bin = latlng_to_cell(lat, lon, RES)
        
        # find debouncing solution if it is an issue naive fix below
        # if (dt <= 5 sec) and (h3_distance(prev_bin, bin) == 1) (reduce bouncing between cells)
        #     continue 

        if(prev_point):

            lat1, lon1 = cur_point
            lat2, lon2 = prev_point

            dt_hours = dt/3600

            implied_speed = haversine_distance_nm(lat1, lon1, lat2, lon2)/dt_hours
        
        if implied_speed > MAX_SPEED:
            prev_time = None
            prev_bin = None
            prev_point = None
            print(f"Impossible speed: {implied_speed} for {entry.get("TYPE")}")
            continue

        if(prev_bin):
            if(cur_bin == prev_bin):
                
                if entry.get("GROUND_SPEED"):
                    gnd_speed_sum += entry.get("GROUND_SPEED")
                    gnd_speed_count += 1

                if entry.get("ALTITUDE"):
                    alt_sum += entry.get("ALTITUDE")
                    alt_count += 1

                if entry.get("VERTICAL_RATE"):
                    vert_rate_sum += entry.get("VERTICAL_RATE")
                    vert_rate_count += 1

                if entry.get("IAS"):
                    ias_sum += entry.get("IAS")
                    ias_count += 1

                if entry.get("TRACK"):
                    heading_sum += entry.get("TRACK")
                    heading_count += 1

                continue 

            else:

                gnd_speed_ave = safe_div(gnd_speed_sum, gnd_speed_count)  
                alt_ave       = safe_div(alt_sum, alt_count)
                vert_rate_ave = safe_div(vert_rate_sum, vert_rate_count)
                ias_ave       = safe_div(ias_sum, ias_count)
                heading_ave   = safe_div(heading_sum, heading_count)

                # print(f"\ngnd_speed_ave: {gnd_speed_ave}")
                # print(f"alt_ave: {alt_ave}")
                # print(f"vert_rate_ave: {vert_rate_ave}")
                # print(f"ias_ave: {ias_ave}")
                # print(f"heading_ave: {heading_ave}\n")

                #new bin traversal
                bin_traversal_update(conn, cur_bin, airport_cells)

                gnd_speed_sum = 0
                alt_sum = 0
                vert_rate_sum = 0
                ias_sum = 0
                heading_sum = 0

                gnd_speed_count = 0
                alt_count = 0
                vert_rate_count = 0
                ias_count = 0
                heading_count = 0
               

            
        # else
        #     new_bin_traversal += 1 
        #     record transition
        #     record_transition_stats(prev_bin, cur_bin)

        prev_time = cur_time
        prev_bin = cur_bin
        prev_point = cur_point


def bin_traversal_update(conn, h3_cell, airport_cells):

    h3_index = int(h3_cell, 16)

    with conn.cursor() as cur:

        # Fast path:
        # If row already exists, only increment traversal count.
        cur.execute("""
            UPDATE heatmap_bins
            SET traversal_count = traversal_count + 1
            WHERE h3_index = %(h3_index)s
            RETURNING h3_index;
        """, {
            "h3_index": h3_index,
        })

        existing = cur.fetchone()

        # Existing row updated successfully
        if existing:
            conn.commit()
            return

        # NEW CELL ONLY BELOW THIS POINT

        lat_center, lon_center = cell_to_latlng(h3_cell)

        contains_airport = h3_index in airport_cells

        cur.execute("""
            INSERT INTO heatmap_bins (
                h3_index,
                lat_center,
                lon_center,
                contains_airport,
                traversal_count
            )
            VALUES (
                %(h3_index)s,
                %(lat_center)s,
                %(lon_center)s,
                %(contains_airport)s,
                1
            );
        """, {
            "h3_index": h3_index,
            "lat_center": lat_center,
            "lon_center": lon_center,
            "contains_airport": contains_airport,
        })

    conn.commit()


def load_airport_cells(conn):

    with conn.cursor() as cur:

        cur.execute("""
            SELECT DISTINCT h3_index
            FROM airports
            WHERE h3_index IS NOT NULL;
        """)

        return {
            row[0]
            for row in cur.fetchall()
        }

def main():

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    #days = build_date_range(1, "1/10/24", "1/1/26")

    with get_conn() as conn:
       
        create_tables(conn)
        airport_cells = load_airport_cells(conn)

        #for day in days:

        #tar_buffer = download_Tar_File(day, day.year)
        tar_buffer = RAW_DIR/"2024.01.03.tar"

        aircraft_count = get_aircraft_count(tar_buffer)

        print(f"count: {aircraft_count}")

        with alive_bar(aircraft_count) as bar:

            bar.title = 'Processing Aircrafts'

            count = 0
            #for aircraft in aircrafts:
            for member, aircraft_data in iter_aircrafts_from_tar(tar_buffer):
                count += 1
                
                if count > 100:
                    break
            
                bar.text(f"File: {member.name[-11:]}")

                normed_data = normalize_data([aircraft_data])
                determine_routes(conn, normed_data, airport_cells)

                #print(f"data: {normed_data[0]}")

                bar()

        del tar_buffer
        del aircraft_count
        gc.collect()









if __name__ == "__main__":
    main()
