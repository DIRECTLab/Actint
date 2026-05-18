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
MAX_SPEED = 800


def build_date_range(day_delta, start_str, end_str=None):

    start = datetime.strptime(start_str, "%m/%d/%y")
    end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start
    current = start
    days = []
    while current <= end:
        days.append(current)
        current += timedelta(days=day_delta)
    return days



def get_aircrafts(tar_buffer):

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:

        total_matches = 0
        tar_members = []

        for member in tar.getmembers():
            if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                
                total_matches = total_matches + 1
                tar_members.append(member)


    return total_matches, tar_members



def get_aircraft_data(tar_buffer, member): 
    
    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:

        f = tar.extractfile(member)
        if f:
            with gzip.open(f, 'rt', encoding='utf-8') as gz:
                try:
                    data = json.load(gz)
                    
                except (json.JSONDecodeError, gzip.BadGzipFile):
                    print(f"error extracting aircraft {member}")

    return data


def save_Tar(tar_buffer):

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
        tar.extractall(RAW_DIR, filter=lambda tarinfo, _: tarinfo)


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



def determine_routes(data):

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
            continue 

        cur_time = entry.get("TIMESTAMP")

        if(prev_time):
            dt = cur_time - prev_time

        print(f'time delta: {dt}')

        if dt <= 0:
            continue

        lat = entry.get("LAT")
        lon = entry.get("LON")

        cur_point = lat, lon

        cur_bin = latlng_to_cell(lat, lon, RES)
        
        # find debouncing solution if it is an issue naive fix below
        # if (dt <= 5 sec) and (h3_distance(prev_bin, bin) == 1) (reduce bouncing between cells)
        #     continue 

        if(prev_point):
            implied_speed = haversine_distance_nm(cur_point, prev_point)/dt
        
        if implied_speed > MAX_SPEED:
            prev_time = None
            prev_bin = None
            prev_point = None
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
                print()
            
        # else
        #     new_bin_traversal += 1 
        #     record transition
        #     record_transition_stats(prev_bin, cur_bin)
        #     prev_bin = cur_bin

        prev_time = cur_time
        prev_bin = cur_bin
        prev_point = cur_point




def main():

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    days = build_date_range(1, "1/10/24", "1/1/26")

    for day in days:

        tar_buffer = download_Tar_File(day, day.year)
        save_Tar(tar_buffer)
        aircraft_count, aircrafts = get_aircrafts(tar_buffer)

        print(f"count: {aircraft_count}")
        print(f"member: {aircrafts[0]}")

        with alive_bar(aircraft_count) as bar:

            bar.title = 'Processing Aircrafts'

            count = 0
            for aircraft in aircrafts:
                count += 1
                
                if count > 100:
                    break

                bar.text(f"File: {aircraft.name[-11:]}")

                aircraft_data = get_aircraft_data(tar_buffer, aircraft)
                normed_data = normalize_data([aircraft_data])
                
                determine_routes(normed_data)
                #print(f"data: {normed_data[0]}")

                bar()

        del tar_buffer
        del aircrafts 
        del aircraft_count
        gc.collect()


    






if __name__ == "__main__":
    main()
