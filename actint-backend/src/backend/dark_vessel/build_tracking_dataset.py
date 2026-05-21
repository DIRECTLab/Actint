"""
Build Tracking Challenge Dataset
=================================
Generates 20 geographic/parametric variants of each of the 13 canonical
hard-tracking scenarios.  Output:

  outputs/tracking_dataset/
    <scenario_name>/
      variant_01.csv … variant_20.csv
    all_scenarios.csv          ← master flat file (all 260 variant CSVs merged)
    manifest.json              ← per-variant metadata

Variants differ in:
  - NumPy RNG seed
  - Geographic region (lat/lon offset applied post-generation)
  - Speed scale factor (±15 %)
  - Scenario-specific timing jitter

Usage:
    python build_tracking_dataset.py
    python build_tracking_dataset.py --output-dir /tmp/dataset
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── make sure src/ is importable ─────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import src.tracking_scenarios as _scen_mod
from src.tracking_scenarios import _GENERATORS, SCENARIO_LABELS


# ══════════════════════════════════════════════════════════════════════════════
# Variant configuration table
# 20 rows — each defines a geographic region + seed + speed multiplier.
# lat_off / lon_off are added to every position in the generated track.
# The offsets place scenarios in realistic maritime operating areas.
# ══════════════════════════════════════════════════════════════════════════════

VARIANTS = [
    # id   region_label                lat_off   lon_off   seed   spd_scale
    ( 1,  "Singapore Strait",           0.00,     0.00,   1001,   1.00),
    ( 2,  "Malacca Strait (N)",         3.50,    -1.80,   1002,   0.95),
    ( 3,  "South China Sea",            8.00,     7.50,   1003,   1.05),
    ( 4,  "Gulf of Thailand",           8.50,     0.50,   1004,   0.90),
    ( 5,  "Bay of Bengal",             12.00,   -14.00,   1005,   1.10),
    ( 6,  "Arabian Sea",               15.00,   -38.00,   1006,   1.08),
    ( 7,  "Red Sea",                   20.00,   -65.00,   1007,   0.92),
    ( 8,  "Gulf of Aden",              10.00,   -61.00,   1008,   1.03),
    ( 9,  "West Africa (Gulf Guinea)", -2.00,   -65.00,   1009,   0.97),
    (10,  "Mediterranean (W)",         35.00,   -67.00,   1010,   1.12),
    (11,  "North Sea",                 52.00,   -66.50,   1011,   0.88),
    (12,  "Baltic Sea",                56.00,   -81.00,   1012,   0.93),
    (13,  "Caribbean Sea",             13.00,   -76.00,   1013,   1.06),
    (14,  "Gulf of Mexico",            23.00,   -80.00,   1014,   0.96),
    (15,  "US East Coast (approaches)",35.00,   -74.00,   1015,   1.02),
    (16,  "Pacific (Hawaii area)",      20.00,  -62.00,   1016,   1.15),
    (17,  "Sea of Japan",              37.00,    27.00,   1017,   0.85),
    (18,  "Korea Strait",              34.00,    25.50,   1018,   1.07),
    (19,  "Taiwan Strait",             22.00,    17.00,   1019,   0.98),
    (20,  "Indian Ocean (central)",    -8.00,   -37.00,   1020,   1.04),
]


def _patch_rng(seed: int) -> None:
    """Replace the module-level RNG used by all _propagate() calls."""
    _scen_mod._RNG = np.random.default_rng(seed)


def _apply_geo_offset(df: pd.DataFrame, lat_off: float, lon_off: float) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = df["lat"] + lat_off
    df["lon"] = df["lon"] + lon_off
    return df


def _apply_speed_scale(df: pd.DataFrame, scale: float) -> pd.DataFrame:
    """Scale SOG values; clamp NaNs (dark rows) gracefully."""
    df = df.copy()
    df["sog"] = df["sog"] * scale
    return df


def _generate_variant(scenario_name: str, variant: tuple) -> pd.DataFrame:
    vid, region, lat_off, lon_off, seed, spd_scale = variant

    _patch_rng(seed)
    gen_fn = _GENERATORS[scenario_name]
    df = gen_fn()

    df = _apply_geo_offset(df, lat_off, lon_off)
    df = _apply_speed_scale(df, spd_scale)

    df["variant_id"]     = vid
    df["region"]         = region
    df["rng_seed"]       = seed
    df["speed_scale"]    = spd_scale

    return df


def build_dataset(output_dir: str = "outputs/tracking_dataset") -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    master_frames = []
    manifest = {
        "generated_at":   pd.Timestamp.utcnow().isoformat(),
        "format_version": "2.0",
        "n_scenario_types": len(_GENERATORS),
        "n_variants_per_type": len(VARIANTS),
        "total_variant_files": len(_GENERATORS) * len(VARIANTS),
        "column_schema": {
            "mmsi":         "int — vessel MMSI (may repeat for clone/spoofing scenarios)",
            "timestamp":    "ISO 8601 UTC — sort this column for replay",
            "lat":          "float — decimal degrees WGS-84",
            "lon":          "float — decimal degrees WGS-84",
            "sog":          "float — speed over ground, knots (NaN in dark gaps)",
            "cog":          "float — course over ground, degrees (NaN in dark gaps)",
            "heading":      "float — true heading, degrees (NaN in dark gaps)",
            "sensor_type":  "str — ais | satellite_ais | radar | eo | none",
            "true_activity":"str — ground-truth activity label",
            "vessel_type":  "str — vessel type key",
            "nav_status":   "int — AIS nav status code",
            "scenario":     "str — canonical scenario key",
            "track_id":     "str — per-scenario vessel identifier",
            "is_dark":      "bool — True for AIS-gap / dead-reckoning rows",
            "variant_id":   "int — 1-20, identifies the geographic/parametric variant",
            "region":       "str — maritime region label for this variant",
            "rng_seed":     "int — numpy seed used; reproducible with same seed",
            "speed_scale":  "float — multiplier applied to all SOG values",
        },
        "variants": {v[0]: {"region": v[1], "lat_offset": v[2], "lon_offset": v[3],
                             "seed": v[4], "speed_scale": v[5]}
                     for v in VARIANTS},
        "scenarios": {},
    }

    for scenario_name in _GENERATORS:
        scen_dir = out / scenario_name
        scen_dir.mkdir(exist_ok=True)
        scenario_frames = []
        manifest["scenarios"][scenario_name] = {
            "label":    SCENARIO_LABELS.get(scenario_name, scenario_name),
            "variants": {},
        }

        for variant in VARIANTS:
            vid = variant[0]
            print(f"  generating {scenario_name} variant {vid:02d}/{len(VARIANTS)} "
                  f"({variant[1]}) ...", flush=True)

            df = _generate_variant(scenario_name, variant)

            # Normalise timestamps to ISO strings
            if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            df = df.sort_values("timestamp").reset_index(drop=True)

            csv_path = scen_dir / f"variant_{vid:02d}.csv"
            df.to_csv(csv_path, index=False)

            ts = pd.to_datetime(df["timestamp"])
            dur_min = float((ts.max() - ts.min()).total_seconds() / 60)

            manifest["scenarios"][scenario_name]["variants"][vid] = {
                "file":             str(csv_path.relative_to(out)),
                "region":           variant[1],
                "n_pings":          int(len(df)),
                "n_pings_live":     int((~df["is_dark"]).sum()),
                "n_tracks":         int(df["track_id"].nunique()),
                "n_vessels":        int(df["mmsi"].nunique()),
                "t_start":          ts.min().isoformat(),
                "t_end":            ts.max().isoformat(),
                "duration_minutes": round(dur_min, 1),
                "vessel_types":     sorted(df["vessel_type"].dropna().unique().tolist()),
                "activities":       sorted(df["true_activity"].dropna().unique().tolist()),
                "sensor_types":     sorted(df["sensor_type"].dropna().unique().tolist()),
                "has_dark_pings":   bool(df["is_dark"].any()),
                "lat_range":        [round(float(df["lat"].min()), 4),
                                     round(float(df["lat"].max()), 4)],
                "lon_range":        [round(float(df["lon"].min()), 4),
                                     round(float(df["lon"].max()), 4)],
            }

            scenario_frames.append(df)
            master_frames.append(df)

        # One merged CSV per scenario type (all 20 variants)
        scen_all = pd.concat(scenario_frames, ignore_index=True)
        scen_all_path = out / f"{scenario_name}_all_variants.csv"
        scen_all.to_csv(scen_all_path, index=False)
        manifest["scenarios"][scenario_name]["merged_file"] = \
            str(scen_all_path.relative_to(out))
        manifest["scenarios"][scenario_name]["total_pings"] = int(len(scen_all))

        print(f"  → {scenario_name}: {len(scen_all):,} pings across "
              f"{len(VARIANTS)} variants\n")

    # Master flat file
    print("Writing master CSV …")
    master = pd.concat(master_frames, ignore_index=True)
    master_path = out / "all_scenarios.csv"
    master.to_csv(master_path, index=False)
    manifest["total_pings"] = int(len(master))
    print(f"  all_scenarios.csv: {len(master):,} rows")

    # Manifest
    manifest_path = out / "manifest.json"
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"\nDataset written to: {out}/")
    print(f"Manifest:           {manifest_path}")
    print(f"Total pings:        {len(master):,}")
    return str(manifest_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build tracking challenge dataset")
    parser.add_argument("--output-dir", default="outputs/tracking_dataset",
                        help="Output directory (default: outputs/tracking_dataset)")
    args = parser.parse_args()

    print(f"Building dataset — {len(_GENERATORS)} scenario types × "
          f"{len(VARIANTS)} variants = "
          f"{len(_GENERATORS) * len(VARIANTS)} variant files\n")
    build_dataset(args.output_dir)
