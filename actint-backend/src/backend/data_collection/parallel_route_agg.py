"""
parallel pipeline design

single continuous ordered downloader 
    downloads days continuously and keeps a max of 4 days stored at a time in the queue
job dispatcher
    gets next day from the queue and splits it into the aircraft trace files for that day
    gets the trace file for each aircraft and passes it to a worker based on ICAO hash
workers - processes
    build aggregate data to insert, queues this data with a flush counter
    has continued state storage for it's aircraft (process doesn't die and restart at all)
DB inserter
    takes data from the queue and runs a batch insert to the postgres DB 
    single inserter to avoid deadlocks in the DB inserts


"""



from datetime import datetime, timedelta
from alive_progress import alive_bar
import tarfile
import gzip
import json
from pathlib import Path

from h3 import cell_to_latlng, latlng_to_cell
from backend.mcp_servers.adsb.helpers.adsb_locations import get_conn
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm

from contextlib import nullcontext
import re
import requests
import io
import gc

from dataclasses import dataclass
from collections import defaultdict
import math

import multiprocessing as mp
from dateutil.relativedelta import relativedelta 

import setproctitle
import hashlib
import time



DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"

LOG_DIR = Path(__file__).parent / "logging"
PIPELINELOG = LOG_DIR / "pipeline.log"
LOG = LOG_DIR / "log.log"

BASE_URL = "https://github.com/adsblol/globe_history_{year}/releases/download"
RES = 7
MAX_SPEED = 2000
OVERNIGHT_GAP = 3600 * 10 #if there is a 10 hour gap in data don't create an edge
FLUSH_SIZE = 150_000



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


def create_tables(conn, num_workers):

    with conn.cursor() as cur:

        for i in range(num_workers):

            cur.execute(f"""
                CREATE UNLOGGED TABLE IF NOT EXISTS route_heatmap_bins_{i} (
            
                    h3_index BIGINT PRIMARY KEY,
                    lat_center DOUBLE PRECISION,
                    lon_center DOUBLE PRECISION,
                    traversal_count BIGINT NOT NULL,
                    contains_airport BOOLEAN
                )
            """)
            cur.execute(f"""
                CREATE UNLOGGED TABLE IF NOT EXISTS route_segments_{i} (
            
                    start_bin BIGINT NOT NULL,
                    end_bin BIGINT NOT NULL,
                    transition_count BIGINT NOT NULL,
                        
                    PRIMARY KEY (start_bin, end_bin)
                )
            """)
            cur.execute(f"""               
                CREATE UNLOGGED TABLE IF NOT EXISTS route_segment_stats_{i} (
                        
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
                )
                PARTITION BY HASH (start_bin, end_bin);
            """)

    conn.commit()



def create_hash_partitions(conn, base_table="route_segment_stats", num_partitions=16):
    """
    Creates a hash-partitioned table and N partitions for (start_bin, end_bin).
    """
    with conn.cursor() as cur:

        # 2. Create partitions
        for i in range(num_partitions):
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {base_table}_p{i}
                PARTITION OF {base_table}
                FOR VALUES WITH (MODULUS {num_partitions}, REMAINDER {i});
            """)

    conn.commit()


def create_unlogged_hash_partitions(conn, base_table="route_segment_stats", num_partitions=16):
    """
    Creates a hash-partitioned table and N partitions for (start_bin, end_bin).
    """
    with conn.cursor() as cur:

        # 2. Create partitions
        for i in range(num_partitions):
            cur.execute(f"""
                CREATE UNLOGGED TABLE IF NOT EXISTS {base_table}_p{i}
                PARTITION OF {base_table}
                FOR VALUES WITH (MODULUS {num_partitions}, REMAINDER {i});
            """)

    conn.commit()

# def create_monthly_partitions(conn, start_str, end_str=None):

#     cur = conn.cursor()

#     # parse inputs (fixed bug: no variable shadowing)
#     start = datetime.strptime(start_str, "%m/%d/%y")
#     end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start

#     # normalize to month boundaries
#     current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#     end_boundary = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

#     # create monthly partitions
#     while current < end_boundary:
#         next_month = current + relativedelta(months=1)

#         table_name = f"route_segment_stats{current.strftime('%Y_%m')}"
#         start_bound = current.strftime('%Y-%m-%d')
#         end_bound = next_month.strftime('%Y-%m-%d')

#         query = f"""
#         CREATE TABLE IF NOT EXISTS {table_name}
#         PARTITION OF route_segment_stats
#         FOR VALUES FROM ('{start_bound}') TO ('{end_bound}');
#         """

#         cur.execute(query)

#         current = next_month

#     # DEFAULT partition (catch-all)
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS route_segment_stats_default
#         PARTITION OF route_segment_stats
#         DEFAULT;
#     """)

#     conn.commit()



# def get_aircraft_count(tar_buffer):

#     with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
#     #with tarfile.open(tar_buffer, mode="r:*") as tar:

#         total_matches = 0

#         for member in tar.getmembers():
#             if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                
#                 total_matches = total_matches + 1

#     return total_matches



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



def determine_routes(item, worker, airport_cells):

    if not item:
        print("no flight data")
        return

    heatmap_batch = defaultdict(int)
    segment_batch = defaultdict(int)
    stats_batch = {}

    with (
            get_conn() as conn1,
            get_conn() as conn2,
            get_conn() as conn3,
        ):

        def flush():
            if heatmap_batch:
                flush_heatmap_batch(conn1, heatmap_batch, airport_cells, worker)
                heatmap_batch.clear()

            if segment_batch:
                flush_segment_batch(conn2, segment_batch, worker)
                segment_batch.clear()

            if stats_batch:
                flush_route_segment_stats(conn3, stats_batch, worker)
                stats_batch.clear()

            conn1.commit()
            conn2.commit()
            conn3.commit()

        for entry in item:

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
                #day = datetime.fromtimestamp(cur_time)

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



def flush_route_segment_stats(conn, batch, worker):

    rows = []
    table_name = f"route_segment_stats_{worker}"

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

        cur.executemany(f"""
            INSERT INTO {table_name} (
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

                gnd_speed_sum = {table_name}.gnd_speed_sum + EXCLUDED.gnd_speed_sum,
                gnd_speed_count = {table_name}.gnd_speed_count + EXCLUDED.gnd_speed_count,

                vert_rate_sum = {table_name}.vert_rate_sum + EXCLUDED.vert_rate_sum,
                vert_rate_count = {table_name}.vert_rate_count + EXCLUDED.vert_rate_count,

                ias_sum = {table_name}.ias_sum + EXCLUDED.ias_sum,
                ias_count = {table_name}.ias_count + EXCLUDED.ias_count,

                heading_sin_sum = {table_name}.heading_sin_sum + EXCLUDED.heading_sin_sum,
                heading_cos_sum = {table_name}.heading_cos_sum + EXCLUDED.heading_cos_sum,
                heading_count = {table_name}.heading_count + EXCLUDED.heading_count
        """, rows)




def flush_heatmap_batch(conn, heatmap_batch, airport_cells, worker):

    if not heatmap_batch:
        return

    table_name = f"route_heatmap_bins_{worker}"
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

        cur.executemany(f"""
            INSERT INTO {table_name} (
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
                    {table_name}.traversal_count
                    + EXCLUDED.traversal_count
        """, rows)




def flush_segment_batch(conn, segment_batch, worker):

    if not segment_batch:
        return

    table_name = f"route_segments_{worker}"
    rows = []

    for (start_bin, end_bin), transition_count in segment_batch.items():

        rows.append((
            int(start_bin, 16),
            int(end_bin, 16),
            transition_count
        ))

    with conn.cursor() as cur:

        cur.executemany(f"""
            INSERT INTO {table_name} (
                start_bin,
                end_bin,
                transition_count
            )
            VALUES (%s, %s, %s)

            ON CONFLICT (start_bin, end_bin)
            DO UPDATE SET
                transition_count =
                    {table_name}.transition_count
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




def worker_loop(worker_num, in_queue):

    setproctitle.setproctitle(f"route-worker-{worker_num}")

    while True:

        try: 

            with get_conn() as conn1:
                airport_cells = load_airport_cells(conn1)

            item = in_queue.get()
            counter = 0
            if item == "STOP":
                break

            determine_routes(item, worker_num, airport_cells)
            counter += 1

            if counter % 100 == 0:
                log(f"route_worker_{worker_num} counter: {counter}")

        except Exception as e:
            log(f"DB writer error: {e}")



def downloader_loop(day_queue, days):

    setproctitle.setproctitle("route-downloader")
    
    queued_count = 0

    rate_window_start = time.time()
    last_rate_log = time.time()


    for day in days:
        
        start_time = time.time()
        
        tar_buffer = download_Tar_File(day, day.year, show_bar=False)

        download_end_time = time.time()
        download_dt = download_end_time - start_time
        download_dt_minutes = download_dt / (60)
        
        log(f"day: {day} took {download_dt_minutes:.2f} minutes to download")


        for member, aircraft_data in iter_aircrafts_from_tar(tar_buffer):
            
            normed = normalize_data([aircraft_data])

            day_queue.put(normed)
            queued_count += 1
            current_time = time.time()

            #log(f"queued: {day} member: {member.name}")

            # LOG RATE EVERY 15 SECONDS
            if current_time - last_rate_log >= 15:

                elapsed = current_time - rate_window_start

                rate = queued_count / elapsed if elapsed > 0 else 0

                log(
                    f"queue_rate={rate:.2f} items/sec "
                    f"queued={queued_count} "
                    f"day_queue_size={day_queue.qsize()}"
                )

                # RESET WINDOW
                queued_count = 0
                rate_window_start = current_time
                last_rate_log = current_time

        del tar_buffer
        gc.collect()

        end_time = time.time()
        dt = end_time - start_time
        dt_minutes = dt / (60)
        log(f"\nday: {day} took {dt_minutes:.2f} minutes to process\n")

    day_queue.put("STOP")



def dispatcher_loop(day_queue, worker_queues, num_workers):
    
    setproctitle.setproctitle("route-dispatcher")

    def shard(icao):
        return int(hashlib.md5(icao.encode()).hexdigest(), 16) % num_workers

    while True:
        
        try:
            item = day_queue.get()

            if item == "STOP":
                break

            entry = item[0]

            icao = entry.get("ICAO")
            if not icao or str(icao).startswith("~"):
                continue

            worker_id = shard(icao)

            worker_queues[worker_id].put(item)

        except Exception as e:
            log(f"Dispatcher error: {e}")



def db_writer_loop(db_queue):

    setproctitle.setproctitle("route-DB-writer")

    try: 
        with (
            get_conn() as conn1,
            get_conn() as conn2,
            get_conn() as conn3,
        ):

            airport_cells = load_airport_cells(conn1)

            heatmap = defaultdict(int)
            segment = defaultdict(int)
            stats = {}

            def flush():
                if heatmap:
                    #print(f"flushing heatmap")
                    flush_heatmap_batch(conn1, heatmap, airport_cells)
                    heatmap.clear()

                if segment:
                    #print(f"flushing segments")
                    flush_segment_batch(conn2, segment)
                    segment.clear()

                if stats:
                    #print(f"flushing stats")
                    flush_route_segment_stats(conn3, stats)
                    stats.clear()

                conn1.commit()
                conn2.commit()
                conn3.commit()

            while True:
                start_time = time.time_ns()

                item = db_queue.get()

                if item == "STOP":
                    break

                kind, payload = item

                if kind == "heatmap":
                    for k, v in payload.items():
                        heatmap[k] += v

                elif kind == "segment":
                    for k, v in payload.items():
                        segment[k] += v

                elif kind == "stats":
                    for k, v in payload.items():
                        if k not in stats:
                            stats[k] = RouteStatsAccumulator()
                        stats[k].merge(v)

                if (
                    len(segment) >= FLUSH_SIZE or
                    len(heatmap) >= FLUSH_SIZE or
                    len(stats) >= FLUSH_SIZE
                ):
                    #print(f"flushing {len(heatmap)} heatmap entries")
                    flush()

                end_time = time.time_ns()
                dt = end_time - start_time
                #print(f"db_writer loop dt: {dt}")

            #print(f"flushing {len(heatmap)} heatmap entries")
            flush()

    except Exception as e:
        log(f"DB writer error: {e}")



def print_pipeline_stats(day_queue, worker_queues, counter=None):

    workers = [
        q.qsize()
        for q in worker_queues
    ]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats = (
        f"[{timestamp}] "
        f"day_q={day_queue.qsize()} | \t"
        #f"db_q={db_queue.qsize()} | \t"
        f"workers={workers}"
    )

    if counter is not None:
        stats += f" | aircraft_processed={counter.value}"

    #print(stats, flush=True)

    with open(PIPELINELOG, "a") as f:
        f.write(stats + "\n")



def log(*args, sep=" ", end="\n"):

    message = sep.join(str(arg) for arg in args) + end

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{timestamp}] {message}"

    print(line, end="", flush=True)

    with open(LOG, "a") as f:
        f.write(line)



def merge_worker_tables(conn, num_workers):
    
    log(f"starting final merge")
    with conn.cursor() as cur:

        #create main tables

        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_heatmap_bins (
        
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
            CREATE TABLE IF NOT EXISTS route_segment_stats (
                    
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
            )
            PARTITION BY HASH (start_bin, end_bin);
        """)

        conn.commit()

        create_hash_partitions(conn, base_table=f"route_segment_stats")
        conn.commit()

        # -------------------------
        # HEATMAP MERGE
        # # -------------------------
        # log(f"starting heatmap merge")
        # heatmap_union = " UNION ALL ".join(
        #     f"SELECT h3_index, lat_center, lon_center, traversal_count, contains_airport "
        #     f"FROM route_heatmap_bins_{i}"
        #     for i in range(num_workers)
        # )

        # cur.execute(f"""
        #     INSERT INTO route_heatmap_bins (h3_index, lat_center, lon_center, traversal_count, contains_airport)
        #     SELECT 
        #         h3_index,
        #         MIN(lat_center) AS lat_center,
        #         MIN(lon_center) AS lon_center,
        #         SUM(traversal_count) AS traversal_count,
        #         BOOL_OR(contains_airport) AS contains_airport
        #     FROM ({heatmap_union}) AS all_bins
        #     GROUP BY h3_index
        #     ON CONFLICT (h3_index)
        #     DO UPDATE SET
        #         traversal_count = route_heatmap_bins.traversal_count + EXCLUDED.traversal_count,
        #         contains_airport = route_heatmap_bins.contains_airport OR EXCLUDED.contains_airport;
        # """)
        # conn.commit()

        # for i in range(num_workers):
        #     cur.execute(f"DROP TABLE IF EXISTS route_heatmap_bins_{i} CASCADE;")

        # conn.commit()
        # log(f"finished heatmap merge")
        # -------------------------
        # SEGMENTS MERGE
        # -------------------------
        for i in range(num_workers):

            log(f"merging segment worker {i}")

            cur.execute(f"""
                INSERT INTO route_segments (
                    start_bin,
                    end_bin,
                    transition_count
                )
                SELECT
                    start_bin,
                    end_bin,
                    transition_count
                FROM route_segments_{i}

                ON CONFLICT (start_bin, end_bin)
                DO UPDATE SET
                    transition_count =
                        route_segments.transition_count
                        + EXCLUDED.transition_count
            """)

            conn.commit()
     
        for i in range(num_workers):
            cur.execute(f"DROP TABLE IF EXISTS route_segments_{i} CASCADE;")
        conn.commit()

        log(f"finished route segment merge")

        # -------------------------
        # STATS MERGE
        # -------------------------
        log(f"starting route stats merge")

        for i in range(num_workers):

            log(f"merging stats worker {i}")

            cur.execute(f"""
                INSERT INTO route_segment_stats (
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
                SELECT
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
                FROM route_segment_stats_{i}
                ON CONFLICT (start_bin, end_bin, aircraft_type, altitude_band) DO UPDATE SET
                    gnd_speed_sum = route_segment_stats.gnd_speed_sum + EXCLUDED.gnd_speed_sum,
                    gnd_speed_count = route_segment_stats.gnd_speed_count + EXCLUDED.gnd_speed_count,
                    vert_rate_sum = route_segment_stats.vert_rate_sum + EXCLUDED.vert_rate_sum,
                    vert_rate_count = route_segment_stats.vert_rate_count + EXCLUDED.vert_rate_count,
                    ias_sum = route_segment_stats.ias_sum + EXCLUDED.ias_sum,
                    ias_count = route_segment_stats.ias_count + EXCLUDED.ias_count,
                    heading_sin_sum = route_segment_stats.heading_sin_sum + EXCLUDED.heading_sin_sum,
                    heading_cos_sum = route_segment_stats.heading_cos_sum + EXCLUDED.heading_cos_sum,
                    heading_count = route_segment_stats.heading_count + EXCLUDED.heading_count;
            """)

            conn.commit()

        for i in range(num_workers):
            cur.execute(f"DROP TABLE IF EXISTS route_segment_stats_{i} CASCADE;")
        conn.commit()

    conn.commit()
    log(f"finished route stats merge")

    log(f"finished final merge")



def main():
    NUM_WORKERS = 6

    start_day = "4/1/26"
    end_day = "5/1/26"

    Path(LOG).unlink(missing_ok=True)
    Path(PIPELINELOG).unlink(missing_ok=True)

    days = build_date_range(1, start_day, end_day)

    with get_conn() as conn:
        create_tables(conn, NUM_WORKERS)
        for i in range(NUM_WORKERS):
            create_unlogged_hash_partitions(conn, base_table=f"route_segment_stats_{i}")
        #create_monthly_partitions(conn, start_day, end_day)

    mp.set_start_method("spawn")

    day_queue = mp.Queue(maxsize=1000)
    #db_queue = mp.Queue(maxsize=1000)

    worker_queues = [
        mp.Queue(maxsize=100) for _ in range(NUM_WORKERS)
    ]

    workers = [
        mp.Process(target=worker_loop, args=(i, worker_queues[i]), name=f"route-worker-{i}")
        for i in range(NUM_WORKERS)
    ]

    dispatcher = mp.Process(
        target=dispatcher_loop,
        args=(day_queue, worker_queues, NUM_WORKERS),
        name="route-dispatcher"
    )

    # db_writer = mp.Process(
    #     target=db_writer_loop,
    #     args=(db_queue,),
    #     name="route-DB-writer"
    # )

    downloader = mp.Process(
        target=downloader_loop,
        args=(day_queue, days),
        name="route-downloader"
    )

    #Start up
    for w in workers:
        w.start()

    dispatcher.start()
    #db_writer.start()
    downloader.start()

    #Logging
    while True:

        print_pipeline_stats(
            day_queue,
            #db_queue,
            worker_queues
        )

        if not any([
            downloader.is_alive(),
            dispatcher.is_alive(),
            #db_writer.is_alive(),
            *[w.is_alive() for w in workers]
        ]):
            break

        time.sleep(15)

    #Shutdown process
    downloader.join()

    day_queue.put("STOP")
    dispatcher.join()

    for q in worker_queues:
        q.put("STOP")

    for w in workers:
        w.join()

    #final merge
    merge_worker_tables(conn,NUM_WORKERS)

    #db_queue.put("STOP")
    #db_writer.join()



if __name__ == "__main__":
    with get_conn() as conn:
        merge_worker_tables(conn, 6)
    #main()