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

from dataclasses import dataclass
from collections import defaultdict
import math



DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"

BASE_URL = "https://github.com/adsblol/globe_history_{year}/releases/download"
RES = 7
MAX_SPEED = 2000
OVERNIGHT_GAP = 3600 * 10 #if there is a 10 hour gap in data don't create an edge
FLUSH_SIZE = 100_000



@dataclass
class RouteStatsAccumulator:

    gnd_speed_sum: float = 0
    alt_sum: float = 0
    vert_rate_sum: float = 0
    ias_sum: float = 0

    gnd_speed_count: int = 0
    alt_count: int = 0
    vert_rate_count: int = 0
    ias_count: int = 0

    # circular heading accumulator 
    heading_sin_sum: float = 0.0
    heading_cos_sum: float = 0.0
    heading_count: int = 0

  
    # ADD SAMPLE
    def add(self, entry):

        if entry.get("GROUND_SPEED") is not None:
            self.gnd_speed_sum += entry["GROUND_SPEED"]
            self.gnd_speed_count += 1

        if entry.get("ALTITUDE") is not None:
            self.alt_sum += entry["ALTITUDE"]
            self.alt_count += 1

        if entry.get("VERTICAL_RATE") is not None:
            self.vert_rate_sum += entry["VERTICAL_RATE"]
            self.vert_rate_count += 1

        if entry.get("IAS") is not None:
            self.ias_sum += entry["IAS"]
            self.ias_count += 1


        # CIRCULAR HEADING HANDLING
        heading = entry.get("TRACK")
        if heading is not None:

            theta = math.radians(heading)

            self.heading_sin_sum += math.sin(theta)
            self.heading_cos_sum += math.cos(theta)
            self.heading_count += 1


    # LINEAR AVERAGES
    def averages(self):

        return {
            "gnd_speed": safe_div(self.gnd_speed_sum, self.gnd_speed_count),
            "altitude": safe_div(self.alt_sum, self.alt_count),
            "vert_rate": safe_div(self.vert_rate_sum, self.vert_rate_count),
            "ias": safe_div(self.ias_sum, self.ias_count),

            # circular mean
            "heading": self.mean_heading()
        }

  
    # CIRCULAR MEAN HEADING
    def mean_heading(self):

        if self.heading_count == 0:
            return 0.0

        angle = math.atan2(self.heading_sin_sum, self.heading_cos_sum)
        return math.degrees(angle) % 360

    # RESULTANT LENGTH R
    def heading_R(self):

        if self.heading_count == 0:
            return 0.0

        return math.sqrt(
            self.heading_sin_sum ** 2 +
            self.heading_cos_sum ** 2
        ) / self.heading_count

    # RESET
    def reset(self):

        self.gnd_speed_sum = 0
        self.alt_sum = 0
        self.vert_rate_sum = 0
        self.ias_sum = 0

        self.gnd_speed_count = 0
        self.alt_count = 0
        self.vert_rate_count = 0
        self.ias_count = 0

        self.heading_sin_sum = 0.0
        self.heading_cos_sum = 0.0
        self.heading_count = 0

    # MERGE
    def merge(self, other):

        self.gnd_speed_sum += other.gnd_speed_sum
        self.alt_sum += other.alt_sum
        self.vert_rate_sum += other.vert_rate_sum
        self.ias_sum += other.ias_sum

        self.gnd_speed_count += other.gnd_speed_count
        self.alt_count += other.alt_count
        self.vert_rate_count += other.vert_rate_count
        self.ias_count += other.ias_count

        self.heading_sin_sum += other.heading_sin_sum
        self.heading_cos_sum += other.heading_cos_sum
        self.heading_count += other.heading_count



def safe_div(numerator, denominator):
    return numerator / denominator if denominator else 0.0



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
        
                start_bin BIGINT NOT NULL,
                end_bin BIGINT NOT NULL,
                transition_count BIGINT NOT NULL,
                    
                PRIMARY KEY (start_bin, end_bin)
            )
        """)
        cur.execute("""               
            CREATE TABLE IF NOT EXISTS segment_stats (

                start_bin BIGINT NOT NULL,
                end_bin   BIGINT NOT NULL,

                aircraft_type TEXT NOT NULL,
                altitude_band TEXT NOT NULL,

                gnd_speed_sum REAL DEFAULT 0,
                gnd_speed_count BIGINT DEFAULT 0,

                vert_rate_sum REAL DEFAULT 0,
                vert_rate_count BIGINT DEFAULT 0,

                ias_sum REAL DEFAULT 0,
                ias_count BIGINT DEFAULT 0,

                heading_sin_sum REAL DEFAULT 0,
                heading_cos_sum REAL DEFAULT 0,
                heading_count BIGINT DEFAULT 0,

                PRIMARY KEY (start_bin, end_bin, aircraft_type, altitude_band)
            );
        """)

    conn.commit()


def get_aircraft_count(tar_buffer):

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
    #with tarfile.open(tar_buffer, mode="r:*") as tar:

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



def iter_aircrafts_from_tar(tar_buffer):
    """
    Yields one aircraft JSON object at a time from a tar.gz archive.
    Memory efficient: streams per member.
    """

    pattern = re.compile(r'^./traces/[0-9a-fA-F]{2}/.*\.json$')

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
    #with tarfile.open(tar_path, mode="r:*") as tar:

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



#Global Aircraft state array

class AircraftState:
    def __init__(self):
        self.prev_time = None
        self.prev_bin = None
        self.prev_point = None
        self.cell_stats = RouteStatsAccumulator()
        self.last_cell_stats = RouteStatsAccumulator()

aircraft_state = {}  # ICAO -> AircraftState



def determine_routes(conn, data, airport_cells):

    if not data:
        print("no flight data")
        return

    def flush():
        if heatmap_batch:
            flush_heatmap_batch(conn, heatmap_batch, airport_cells)
            heatmap_batch.clear()

        if segment_batch:
            flush_segment_batch(conn, segment_batch)
            segment_batch.clear()

        if stats_batch:
            flush_segment_stats(conn, stats_batch)
            stats_batch.clear()

        conn.commit()

    heatmap_batch = defaultdict(int)
    segment_batch = defaultdict(int)
    stats_batch = {}

    for entry in data:

        
        # FILTER INVALID RECORDS
        if entry.get("ALTITUDE") is None or entry.get("ALTITUDE") <= 1000:
            continue

        icao = entry.get("ICAO")
        if not icao or str(icao).startswith("~"):
            continue

        state = aircraft_state.setdefault(icao, AircraftState())

        cur_time = entry.get("TIMESTAMP")
        lat = entry.get("LAT")
        lon = entry.get("LON")

        cur_point = lat, lon

        if lat is None or lon is None:
            continue

        cur_bin = latlng_to_cell(lat, lon, RES)

        
        # OVERNIGHT / GAP RESET
        if state.prev_time is not None:
            dt = cur_time - state.prev_time

            if dt <= 0:
                continue

            if dt > OVERNIGHT_GAP:
                state.prev_time = cur_time
                state.prev_bin = None
                state.prev_point = None
                state.cell_stats = RouteStatsAccumulator()
                state.last_cell_stats = RouteStatsAccumulator()
                state.cell_stats.add(entry)
                continue

        
        # SPEED VALIDATION
        if state.prev_point and state.prev_time:
            dt = cur_time - state.prev_time
            dt_hours = dt / 3600

            speed = haversine_distance_nm(
                lat, lon,
                state.prev_point[0], state.prev_point[1]
            ) / dt_hours

            if speed > MAX_SPEED:
                state.prev_time = cur_time
                state.prev_bin = cur_bin
                state.prev_point = cur_point
                state.cell_stats = RouteStatsAccumulator()
                state.last_cell_stats = RouteStatsAccumulator()
                state.cell_stats.add(entry)

        
        # CELL INITIALIZATION
        if state.prev_bin is None:
            state.prev_bin = cur_bin
            state.prev_time = cur_time
            state.prev_point = cur_point
            state.cell_stats = RouteStatsAccumulator()
            state.cell_stats.add(entry)
            continue

        
        # SAME CELL → ACCUMULATE
        if cur_bin == state.prev_bin:
            state.cell_stats.add(entry)

        
        # TRANSITION EVENT
        else:

            heatmap_batch[cur_bin] += 1
            segment_batch[(state.prev_bin, cur_bin)] += 1

            aircraft_type = entry.get("TYPE") or "unknown"
            altitude_band = get_altitude_band(state.cell_stats)

            key = (
                state.prev_bin,
                cur_bin,
                aircraft_type,
                altitude_band
            )

            if key not in stats_batch:
                stats_batch[key] = RouteStatsAccumulator()

            # FULL BIDIRECTIONAL CELL MERGE
            stats_batch[key].merge(state.last_cell_stats)
            stats_batch[key].merge(state.cell_stats)

            # shift window forward
            state.last_cell_stats = state.cell_stats
            state.cell_stats = RouteStatsAccumulator()
            
            state.cell_stats.add(entry)
            state.prev_bin = cur_bin

        
        # UPDATE STATE
        state.prev_time = cur_time
        state.prev_point = cur_point

        
        # FLUSH TRIGGER
        if (
            len(segment_batch) >= FLUSH_SIZE or
            len(heatmap_batch) >= FLUSH_SIZE or
            len(stats_batch) >= FLUSH_SIZE
        ):
            flush()

    flush()



def get_altitude_band(stats, step=10):
    """
    Buckets altitude into FL bands (default 10 FL = 1000 ft bins)
    """

    if stats.alt_count == 0:
        return "FLNONE"

    avg_alt = stats.alt_sum / stats.alt_count

    fl = int(round(avg_alt / 100))

    # bucket it
    fl_band = (fl // step) * step

    return f"FL{fl_band:03d}"



def flush_segment_stats(conn, batch):

    rows = []

    for (start_bin, end_bin, aircraft_type, altitude_band), stats in batch.items():

        rows.append((
            int(start_bin, 16),
            int(end_bin, 16),
            aircraft_type,
            altitude_band,

            stats.gnd_speed_sum,
            stats.gnd_speed_count,

            stats.vert_rate_sum,
            stats.vert_rate_count,

            stats.ias_sum,
            stats.ias_count,

            stats.heading_sin_sum,
            stats.heading_cos_sum,
            stats.heading_count
        ))

    with conn.cursor() as cur:

        cur.executemany("""
            INSERT INTO segment_stats (
                start_bin,
                end_bin,
                aircraft_type,
                altitude_band,

                gnd_speed_sum,
                gnd_speed_count,

                vert_rate_sum,
                vert_rate_count,

                ias_sum,
                ias_count,

                heading_sin_sum,
                heading_cos_sum,
                heading_count
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)

            ON CONFLICT (start_bin, end_bin, aircraft_type, altitude_band)
            DO UPDATE SET

                gnd_speed_sum = segment_stats.gnd_speed_sum + EXCLUDED.gnd_speed_sum,
                gnd_speed_count = segment_stats.gnd_speed_count + EXCLUDED.gnd_speed_count,

                vert_rate_sum = segment_stats.vert_rate_sum + EXCLUDED.vert_rate_sum,
                vert_rate_count = segment_stats.vert_rate_count + EXCLUDED.vert_rate_count,

                ias_sum = segment_stats.ias_sum + EXCLUDED.ias_sum,
                ias_count = segment_stats.ias_count + EXCLUDED.ias_count,

                heading_sin_sum = segment_stats.heading_sin_sum + EXCLUDED.heading_sin_sum,
                heading_cos_sum = segment_stats.heading_cos_sum + EXCLUDED.heading_cos_sum,
                heading_count = segment_stats.heading_count + EXCLUDED.heading_count
        """, rows)



def flush_heatmap_batch(conn, heatmap_batch, airport_cells):

    if not heatmap_batch:
        return

    rows = []

    for h3_cell, traversal_count in heatmap_batch.items():

        h3_index = int(h3_cell, 16)

        lat_center, lon_center = cell_to_latlng(h3_cell)

        contains_airport = h3_index in airport_cells

        rows.append((
            h3_index,
            lat_center,
            lon_center,
            contains_airport,
            traversal_count
        ))

    with conn.cursor() as cur:

        cur.executemany("""
            INSERT INTO heatmap_bins (
                h3_index,
                lat_center,
                lon_center,
                contains_airport,
                traversal_count
            )
            VALUES (%s, %s, %s, %s, %s)

            ON CONFLICT (h3_index)
            DO UPDATE SET
                traversal_count =
                    heatmap_bins.traversal_count
                    + EXCLUDED.traversal_count
        """, rows)




def flush_segment_batch(conn, segment_batch):

    if not segment_batch:
        return

    rows = []

    for (start_bin, end_bin), transition_count in segment_batch.items():

        rows.append((
            int(start_bin, 16),
            int(end_bin, 16),
            transition_count
        ))

    with conn.cursor() as cur:

        cur.executemany("""
            INSERT INTO route_segments (
                start_bin,
                end_bin,
                transition_count
            )
            VALUES (%s, %s, %s)

            ON CONFLICT (start_bin, end_bin)
            DO UPDATE SET
                transition_count =
                    route_segments.transition_count
                    + EXCLUDED.transition_count
        """, rows)




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

    days = build_date_range(1, "5/1/25", "5/1/26")

    with get_conn() as conn:
       
        create_tables(conn)
        airport_cells = load_airport_cells(conn)

        for day in days:

            tar_buffer = download_Tar_File(day, day.year)
            #tar_buffer = RAW_DIR/"2024.01.03.tar"

            aircraft_count = get_aircraft_count(tar_buffer)
            tar_buffer.seek(0) 

            print(f"count: {aircraft_count}")

            with alive_bar(aircraft_count) as bar:

                bar.title = 'Processing Aircrafts'

                #count = 0

                for member, aircraft_data in iter_aircrafts_from_tar(tar_buffer):
                    #count += 1
                    
                    #if count > 10000:
                    #    break
                
                    bar.text(f"File: {member.name[-11:]}")

                    normed_data = normalize_data([aircraft_data])
                    determine_routes(conn, normed_data, airport_cells)

                    bar()

            del tar_buffer
            del aircraft_count
            gc.collect()




if __name__ == "__main__":
    main()
