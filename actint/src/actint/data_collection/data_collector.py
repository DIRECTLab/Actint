"""
General Idea: run this script with date arguments to get ADS-B json data for a give day or range of days

Example:    python data_collector.py --start 3/5/25 --end 3/10/26
            python data_collector.py --start 3/5/25                  //just gets data for start date

Optional arguments: data-out-dir (set output directory to store json data in) defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

Example download links

https://github.com/adsblol/globe_history_2026/releases/download/v2026.03.14-planes-readsb-prod-0/v2026.03.14-planes-readsb-prod-0.tar.aa
https://github.com/adsblol/globe_history_2026/releases/download/v2026.03.14-planes-readsb-prod-0/v2026.03.14-planes-readsb-prod-0.tar.ab
https://github.com/adsblol/globe_history_2024/releases/download/v2024.02.01-planes-readsb-prod-0/v2024.02.01-planes-readsb-prod-0.tar

Pseudo Code

    get start and end dates from arguments
    end date defaults to start date
    optional output directory argument defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

    determine number of days and which days we will be looping through to get data 

    stream tar files to memory
    extract tar files
    loop through trace folder and extract and combine json files (in the tar archive there is a directory called traces with directories 00-ff each has compressed json data)
    normalize the json file (flatten and add keys)
    write normed data to SQL DB
    compile list of aircrafts as entries are saved and write to a table
    embed aircraft table entries into ChromaDB

"""
import argparse
import requests
import tarfile
import gzip
import json
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import io
from alive_progress import alive_bar
import time
import re
import gc

# -------------------------
# Configuration
# -------------------------
DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = DATA_DIR / "processed"
BATCH_SIZE = 5000

BASE_URL = "https://github.com/adsblol/globe_history_{year}/releases/download"


# -------------------------
# Argument parsing
# -------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="ADS-B Data Collector")
    parser.add_argument("--start", required=True, help="Start date MM/DD/YY")
    parser.add_argument("--end", help="End date MM/DD/YY (optional)")
    parser.add_argument("--data-out-dir", type=Path, default=OUT_DIR, help="Output directory for processed data")
    parser.add_argument("--db-file", type=Path, default=DATA_DIR / "adsb.sqlite", help="Output file for SQLite DB")
    return parser.parse_args()


# -------------------------
# Date range
# -------------------------
def build_date_range(start_str, end_str=None):
    start = datetime.strptime(start_str, "%m/%d/%y")
    end = datetime.strptime(end_str, "%m/%d/%y") if end_str else start
    current = start
    days = []
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


# -------------------------
# Downloading TAR to memory
# -------------------------
def download_Tar(day): 
    
    all_records = []

    year = day.year
    tag = f"v{day:%Y.%m.%d}-planes-readsb-prod-0"

    url = f"{BASE_URL.format(year=year)}/{tag}/{tag}.tar"

    parts = []

    with alive_bar(title=f"Getting: {day:%Y.%m.%d} ") as bar:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Found single file")
                parts.append(response.content)

            else:
                print("Using multi-part file")
                for b in "abcdefghijklmnopqrstuvwxyz":
                    part = f"a{b}"
                    url_parts = f"{url}.{part}"

                    r = requests.get(url_parts)
                    if r.status_code == 404:
                        break

                    r.raise_for_status()
                    parts.append(r.content)

            bar()

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    
    if not parts:
        print("No data found")
        return
    
    tar_bytes = b"".join(parts)
    tar_buffer = io.BytesIO(tar_bytes)

    with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
        
        #tar.extractall(RAW_DIR, filter=lambda tarinfo, _: tarinfo) #writes extracted tar to raw data directory (need to add date folder)
        total_matches = 0

        for member in tar.getmembers():
            if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                total_matches = total_matches + 1

        print(f"Total JSON Matches: {total_matches}")

        with alive_bar(total_matches) as bar:

            bar.title = 'Extracting JSON Traces: '

            for member in tar.getmembers():

                # Match files in traces/00-ff/ ending in .json.gz
                #if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name): #all json matched
                if re.match(r'^./traces/00/.*\.json$', member.name): #testing match to reduce number of files
                    f = tar.extractfile(member)
                    if f:
                        with gzip.open(f, 'rt', encoding='utf-8') as gz:
                            try:
                                data = json.load(gz)
                                normed_data = normalize_data([data])
                                all_records.append(normed_data)
                            except (json.JSONDecodeError, gzip.BadGzipFile):
                                continue

                            #clean up unused objects now that all data is saved to all_records
                            del data
                            del gz
                            del f
                            gc.collect()
                            bar()

    # Write the final combined list to a local file
    with open("combined_traces.json", "w", encoding="utf-8") as out_file:
        json.dump(all_records, out_file, indent=4)

    print(f"Done! Saved {len(all_records)} JSON objects to combined_traces.json")



# -------------------------
# Normalize JSON data (flatten and add keys)
# -------------------------
def normalize_data(json_data):

    flattened = []

    for record in json_data:

        base = {
            "ICAO": record.get("icao"),
            "REG_NUM": record.get("r"),
            "TYPE": record.get("t"),
            "DESC": record.get("desc"),
            "DBFLAGS": record.get("dbFlags"),
            "MILITARY": bool(record.get("dbFlags", 0) & 1),
            #"interesting": bool(record.get("dbFlags", 0) & 2),
            #"pia": bool(record.get("dbFlags", 0) & 4),
            #"ladd": bool(record.get("dbFlags", 0) & 8),
            "TIMESTAMP": record.get("timestamp"),
        }

        trace_list = record.get("trace", [])

        for entry in trace_list:
            if not isinstance(entry, list):
                continue

            # unpack with safe indexing
            trace_obj = {
                **base,
                "TIME_OFFSET": entry[0] if len(entry) > 0 else None,
                "LAT": entry[1] if len(entry) > 1 else None,
                "LON": entry[2] if len(entry) > 2 else None,
                "ALTITUDE": entry[3] if len(entry) > 3 else None,
                "GROUND_SPEED": entry[4] if len(entry) > 4 else None,
                "TRACK": entry[5] if len(entry) > 5 else None,
                "FLAGS": entry[6] if len(entry) > 6 else None,
                "VERTICAL_RATE": entry[7] if len(entry) > 7 else None,
                #"aircraft_meta": entry[8] if len(entry) > 8 else None,
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
        
            flattened.append(trace_obj)

    return flattened


# -------------------------
# Main
# -------------------------
def main():
    args = parse_args()
    days = build_date_range(args.start, args.end)

    for day in days:
        print(f"[DATE] {day.date()}")
        download_Tar(day)


if __name__ == "__main__":
    main()