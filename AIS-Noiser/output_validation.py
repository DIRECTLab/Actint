import pandas as pd
import numpy as np
from pathlib import Path
import sys

def validate_noise_application(original_csv: str, output_csv: str):
    """
    Validates that noise and filtering were applied correctly.
    Compares record counts and coordinate drift per MMSI.
    """
    # Load datasets
    df_orig = pd.read_csv(original_csv)
    df_noised = pd.read_csv(output_csv)

    # Convert timestamps to ensure matching logic is consistent
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

    # 2. Positional Difference Analysis
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
    """
    Handles terminal arguments for validation.
    Usage: python validator.py <original_file> <noised_file>
    """
    if len(sys.argv) < 3:
        print("Usage: python validator.py <original_file> <noised_file>")
        sys.exit(1)

    original_path = sys.argv[1]
    noised_path = sys.argv[2]

    # Verify files exist before processing to prevent pandas errors
    if not Path(original_path).is_file():
        print(f"Error: Original file not found at {original_path}")
        sys.exit(1)
        
    if not Path(noised_path).is_file():
        print(f"Error: Noised file not found at {noised_path}")
        sys.exit(1)

    validate_noise_application(original_path, noised_path)

if __name__ == "__main__":
    main()