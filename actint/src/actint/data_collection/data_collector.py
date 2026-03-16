"""
General Idea: run this script with date arguments to get ADS-B json data for a give day or range of days

Example:    python data_collector.py --start 3/5/25 --end 3/10/26
            python data_collector.py --start 3/5/25                  //just gets data for start date

Optional arguments: data-out-dir (set output directory to store json data in) defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

Example download links

https://github.com/adsblol/globe_history_2026/releases/tag/v2026.03.15-planes-readsb-prod-0#assets
https://github.com/adsblol/globe_history_2026/releases/tag/v2026.03.14-planes-readsb-prod-0#assets

https://github.com/adsblol/globe_history_2026/releases/download/v2026.03.14-planes-readsb-prod-0/v2026.03.14-planes-readsb-prod-0.tar.aa
https://github.com/adsblol/globe_history_2026/releases/download/v2026.03.14-planes-readsb-prod-0/v2026.03.14-planes-readsb-prod-0.tar.ab

https://github.com/adsblol/globe_history_2025/releases/download/v2025.12.08-planes-readsb-prod-0/v2025.12.08-planes-readsb-prod-0.tar.ab

https://github.com/adsblol/globe_history_2024/releases/tag/v2024.01.31-planes-readsb-prod-0#assets
https://github.com/adsblol/globe_history_2024/releases/download/v2024.02.01-planes-readsb-prod-0/v2024.02.01-planes-readsb-prod-0.tar

Pseudo Code

main function

    get start and end dates from arguments
    end date defaults to start date
    optional output directory argument defaults to DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

    determine number of days and which days we will be looping through to get data 
        needs to account for multiple months or years
        and leap year in 2024 (feb 29th)

    loop for each day in list of days
        download_day("date") //gets the tar.a* files
        unzip() //finds the tar file in the DATA_DIR and does cat file.tar.a* | tar -xf - -C combined/ to unzip and save to a folder
                //next it will unzip the json files that are zip compressed with command: gzip -dc file.json.gz > ./folder/file.json
        concat_json() //takes the latest uncompressed json files and concatenates them into one file

        
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
# Download helpers
# -------------------------
def download_file(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"[INFO] Skipping existing file: {path.name}")
        return
    print(f"[INFO] Downloading: {url}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)



def download_day(day):
    year = day.year
    tag = f"v{day:%Y.%m.%d}-planes-readsb-prod-0"
    raw_day_dir = RAW_DIR / f"{day:%Y-%m-%d}"
    raw_day_dir.mkdir(parents=True, exist_ok=True)

    files = []

    # First try the single .tar file (no parts)
    single_filename = f"{tag}.tar"
    single_url = f"{BASE_URL.format(year=year)}/{tag}/{single_filename}"
    single_path = raw_day_dir / single_filename

    try:
        download_file(single_url, single_path)
        files.append(single_path)
        return files  # if single .tar exists, no need to check parts
    except requests.HTTPError as e:
        if e.response.status_code != 404:
            raise
        # else, single file doesn't exist → fall back to parts

    # Generate parts dynamically from 'aa' to 'az'
    parts = [f"a{chr(ord('a') + i)}" for i in range(26)]

    for part in parts:
        filename = f"{tag}.tar.{part}"
        url = f"{BASE_URL.format(year=year)}/{tag}/{filename}"
        path = raw_day_dir / filename

        try:
            download_file(url, path)
            files.append(path)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # stop after first missing part
                break
            else:
                raise

    if not files:
        print(f"[WARN] No tar files found for {day:%Y-%m-%d}")
        
    return files


# -------------------------
# Main
# -------------------------
def main():
    args = parse_args()
    days = build_date_range(args.start, args.end)

    for day in days:
        print(f"[DATE] {day.date()}")
        parts = download_day(day)


if __name__ == "__main__":
    main()