import pandas as pd
import numpy as np
from pathlib import Path
import sys

def count_gaps(df: pd.DataFrame, gap_threshold_seconds: int = 30) -> int:
    """
    Identifies gaps in time-series data per MMSI.
    A gap is defined as the time difference between consecutive rows exceeding the threshold.
    """
    # Ensure data is sorted by vessel and then time for accurate diffing
    df = df.sort_values(by=["MMSI", "BaseDateTime"])
    
    # Group by MMSI and calculate the time difference between consecutive rows
    # .diff() returns a Timedelta object
    time_deltas = df.groupby("MMSI")["BaseDateTime"].diff()
    
    # Identify where the delta is greater than the threshold
    # Note: The first row of every group will be NaT (Not a Time), which is handled
    gaps = time_deltas > pd.Timedelta(seconds=gap_threshold_seconds)
    
    return int(gaps.sum())

def validate_noise_application(original_csv: str, output_csv: str):
    """
    Validates that noise and filtering were applied correctly.
    Compares record counts, coordinate drift, and temporal gaps.
    """
    df_orig = pd.read_csv(original_csv)
    df_noised = pd.read_csv(output_csv)

    df_orig["BaseDateTime"] = pd.to_datetime(df_orig["BaseDateTime"])
    df_noised["BaseDateTime"] = pd.to_datetime(df_noised["BaseDateTime"])

    # 1. Record Retention Analysis
    orig_counts = df_orig.groupby("MMSI").size().rename("original_count")
    noised_counts = df_noised.groupby("MMSI").size().rename("noised_count")
    
    stats = pd.concat([orig_counts, noised_counts], axis=1).fillna(0).astype(int)
    stats["retention_rate"] = stats["noised_count"] / stats["original_count"]

    print("--- Record Retention Summary ---")
    print(stats)
    print("\n")

    # 2. Gap Analysis (New Feature)
    gap_size_secs = 10
    orig_gaps = count_gaps(df_orig, gap_size_secs)
    noised_gaps = count_gaps(df_noised, gap_size_secs)

    print(f"--- Temporal Gap Analysis (>{gap_size_secs}s) ---")
    print(f"Gaps in original data: {orig_gaps}")
    print(f"Gaps in noised data:   {noised_gaps}")
    print(f"Additional gaps introduced: {noised_gaps - orig_gaps}")
    print("\n")

    # 3. Positional Difference Analysis
    merged = pd.merge(
        df_orig,
        df_noised,
        on=["MMSI", "BaseDateTime"],
        suffixes=("_orig", "_noised")
    )

    merged["lat_diff"] = merged["LAT_noised"] - merged["LAT_orig"]
    merged["lon_diff"] = merged["LON_noised"] - merged["LON_orig"]
    
    identical_positions = merged[(merged["lat_diff"] == 0) & (merged["lon_diff"] == 0)]
    
    print("--- Positional Variance Summary ---")
    print(f"Total overlapping records analyzed: {len(merged)}")
    
    if not identical_positions.empty:
        print(f"CRITICAL: {len(identical_positions)} records were NOT noised.")
    else:
        print("Success: All analyzed records show coordinate displacement.")

    avg_lat_drift = merged["lat_diff"].abs().mean()
    avg_lon_drift = merged["lon_diff"].abs().mean()
    print(f"Mean Latitude Offset: {avg_lat_drift:.6f}")
    print(f"Mean Longitude Offset: {avg_lon_drift:.6f}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python validator.py <original_file> <noised_file>")
        sys.exit(1)

    original_path = sys.argv[1]
    noised_path = sys.argv[2]

    if not Path(original_path).is_file():
        print(f"Error: Original file not found at {original_path}")
        sys.exit(1)
        
    if not Path(noised_path).is_file():
        print(f"Error: Noised file not found at {noised_path}")
        sys.exit(1)

    validate_noise_application(original_path, noised_path)

if __name__ == "__main__":
    main()