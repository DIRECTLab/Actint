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
        
new design

    get start and end dates from arguments
    end date defaults to start date
    optional output directory argument defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

    determine number of days and which days we will be looping through to get data 

    stream tar files to memory
    extract tar files
    loop through trace folder and extract and combine json files (in the tar archive there is a directory called traces with directories 00-ff each has compressed json data)
    write out json file
    

AI suggested design
        

Start the program
    Read the start date and optional end date from the command-line arguments
    Determine the list of days to process (handle month/year changes and leap years)

For each day in the list:
    Download all parts of the day's tar archive from the server
    Combine the tar parts into a single stream (without writing a big file to disk)
    
    For each JSON.gz file inside the tar stream:
        Open the gzip file as a stream
        For each record in the JSON:
            Flatten or extract the fields needed for the database
            Add the record to a batch

            If the batch reaches a certain size:
                Insert all records in the batch into the SQLite database
                Clear the batch

    After finishing all files:
        If any records remain in the batch:
            Insert them into SQLite

    Optionally:
        Generate embeddings from the records and insert them into ChromaDB

End the program

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

    with alive_bar(title=f"Getting: {day:%Y.%m.%d} ") as bar:
        try:
            response = requests.get(url)
            response.raise_for_status() 

            #bar.text = 'Data fetched successfully!'
            bar()
        except requests.exceptions.RequestException as e:
            #bar.text = f'Request failed: {e}'
            print(f"Request failed: {e}")

    content = response.content 

    content_file = io.BytesIO(content)

    with tarfile.open(fileobj=content_file, mode="r:*") as tar:
        
        #tar.extractall(RAW_DIR, filter=lambda tarinfo, _: tarinfo) #writes extracted tar to raw data directory (need to add date folder)
        total_matches = 0

        for member in tar.getmembers():
            if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name):
                total_matches = total_matches + 1

        print(f"Total JSON Matches: {total_matches}")


        with alive_bar(total_matches) as bar:

            bar.title = 'Extracting JSON Traces: '

            for member in tar.getmembers():
                #print(member.name)

                # Match files in traces/00-ff/ ending in .json.gz
                if re.match(r'^./traces/[0-9a-fA-F]{2}/.*\.json$', member.name): #all json matched
                #if re.match(r'^./traces/00/.*\.json$', member.name): #testing match to reduce number of files
                    #print(f"regex match found: {member.name}")
                    f = tar.extractfile(member)
                    if f:
                        with gzip.open(f, 'rb') as gz:
                            try:
                                data = json.load(gz)
                                # Optional: Add the source filename to the data
                                # data['_source_file'] = member.name
                                all_records.append(data)
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