"""
Real Data Integration — Global Fishing Watch (GFW) 2023

Loads and enriches the engine with:
  1. GFW fleet monthly effort data (fishing hours by 0.1° grid cell, flag, geartype)
  2. GFW vessel registry (96k real fishing vessels: MMSI, gear type, dimensions)

Data source: https://zenodo.org/records/14982712  (CC-BY-NC 4.0)
"""

import numpy as np
import pandas as pd
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "gfw"

# Map GFW gear types → our internal vessel type keys
GFW_GEARTYPE_MAP = {
    "trawlers":            "trawler",
    "fishing":             "trawler",         # generic fishing, often trawl
    "set_longlines":       "longliner",
    "drifting_longlines":  "longliner",
    "fixed_gear":          "longliner",
    "set_gillnets":        "longliner",
    "pole_and_line":       "longliner",
    "squid_jigger":        "longliner",
    "other_purse_seines":  "purse_seiner",
    "tuna_purse_seines":   "purse_seiner",
    "purse_seines":        "purse_seiner",
    "seiners":             "purse_seiner",
    "trollers":            "trawler",
    "pots_and_traps":      "longliner",
    "dredge_fishing":      "trawler",
}

# Month name for reporting
MONTHS = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
          7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}


def load_region_fleet(region_key: str) -> pd.DataFrame:
    """
    Load pre-extracted fleet monthly effort data for a region.
    Returns DataFrame with columns:
      date, year, month, cell_ll_lat, cell_ll_lon, flag, geartype,
      hours, fishing_hours, mmsi_present
    """
    path = DATA_DIR / "regions" / f"{region_key}_fleet_2023.csv"
    if not path.exists():
        raise FileNotFoundError(f"Region fleet data not found: {path}")
    df = pd.read_csv(path)
    df["vessel_type"] = df["geartype"].map(GFW_GEARTYPE_MAP).fillna("other")
    df["cell_lat"]    = df["cell_ll_lat"] + 0.05   # cell centre
    df["cell_lon"]    = df["cell_ll_lon"] + 0.05
    return df


def load_vessel_registry(year: int = 2023) -> pd.DataFrame:
    """
    Load GFW vessel registry for a given year.
    Columns: mmsi, flag_gfw, vessel_class_gfw, length_m_gfw,
             engine_power_kw_gfw, tonnage_gt_gfw, fishing_hours, active_hours
    """
    path = DATA_DIR / "regions" / "vessel_registry_2023.csv"
    if path.exists() and year == 2023:
        df = pd.read_csv(path, low_memory=False)
    else:
        full_path = DATA_DIR / "fishing-vessels-v3.csv"
        df = pd.read_csv(full_path, low_memory=False)
        df = df[df["year"] == year]

    df["vessel_type"] = df["vessel_class_gfw"].map(GFW_GEARTYPE_MAP).fillna("other")
    return df


def region_fishing_stats(region_key: str) -> dict:
    """Return summary statistics for a region from real GFW data."""
    df = load_region_fleet(region_key)
    total_fishing_h = df["fishing_hours"].sum()
    total_hours     = df["hours"].sum()
    fishing_frac    = total_fishing_h / max(total_hours, 1)
    top_flags       = df.groupby("flag")["fishing_hours"].sum().sort_values(ascending=False).head(10)
    top_gears       = df.groupby("geartype")["fishing_hours"].sum().sort_values(ascending=False).head(8)
    monthly         = df.groupby("month")["fishing_hours"].sum()

    # Peak fishing grid cells
    hotspots = (df.groupby(["cell_ll_lat","cell_ll_lon"])["fishing_hours"]
                  .sum().sort_values(ascending=False).head(20))

    return {
        "region": region_key,
        "total_fishing_hours": float(total_fishing_h),
        "total_hours": float(total_hours),
        "fishing_fraction": float(fishing_frac),
        "top_flags": top_flags.to_dict(),
        "top_geartypes": top_gears.to_dict(),
        "monthly_fishing": monthly.to_dict(),
        "peak_hotspots": hotspots.reset_index().to_dict(orient="records"),
        "unique_cells": df[["cell_ll_lat","cell_ll_lon"]].drop_duplicates().__len__(),
        "n_flag_states": df["flag"].nunique(),
        "n_gear_types":  df["geartype"].nunique(),
    }


def get_vessel_length_distribution(gear_type: str = None, year: int = 2023) -> pd.Series:
    """Get real-world vessel length distribution for a gear type."""
    vdf = load_vessel_registry(year)
    if gear_type:
        vdf = vdf[vdf["vessel_type"] == gear_type]
    lengths = vdf["length_m_gfw"].dropna()
    return lengths


def enrich_vessel_classification(vessel_class_gfw: str,
                                  flag: str = None) -> dict:
    """
    Given a GFW vessel class + flag, return enriched classification info
    including typical length range, likely activity, and risk indicators.
    """
    vtype  = GFW_GEARTYPE_MAP.get(vessel_class_gfw, "other")
    vdf = load_vessel_registry()

    mask = vdf["vessel_class_gfw"] == vessel_class_gfw
    if flag:
        mask = mask & (vdf["flag_gfw"] == flag)
    sub = vdf[mask]

    if len(sub) < 5:
        sub = vdf[vdf["vessel_class_gfw"] == vessel_class_gfw]

    length_p25  = float(sub["length_m_gfw"].quantile(0.25)) if len(sub) else 0
    length_p75  = float(sub["length_m_gfw"].quantile(0.75)) if len(sub) else 0
    length_med  = float(sub["length_m_gfw"].median())        if len(sub) else 0

    # High fishing effort vessels (fishing_hours / active_hours ratio)
    sub2 = sub.copy()
    sub2["effort_ratio"] = sub2["fishing_hours"] / (sub2["active_hours"] + 1e-6)
    effort_ratio = float(sub2["effort_ratio"].median()) if len(sub2) else 0

    return {
        "vessel_type":   vtype,
        "gfw_class":     vessel_class_gfw,
        "n_vessels":     len(sub),
        "length_p25_m":  round(length_p25, 1),
        "length_p75_m":  round(length_p75, 1),
        "length_med_m":  round(length_med, 1),
        "effort_ratio":  round(effort_ratio, 3),
        "likely_activity": "fishing" if effort_ratio > 0.2 else "transit",
    }


def build_real_data_heatmap(region_key: str) -> pd.DataFrame:
    """
    Build a per-cell fishing intensity grid from GFW data.
    Returns: cell_lat, cell_lon, total_fishing_hours, peak_month,
             dominant_gear, dominant_flag, intensity_norm (0-1)
    """
    df = load_region_fleet(region_key)
    agg = (df.groupby(["cell_lat", "cell_lon"])
             .agg(
                total_fishing_hours=("fishing_hours", "sum"),
                total_hours=("hours", "sum"),
                dominant_gear=("geartype", lambda x: x.value_counts().index[0]),
                dominant_flag=("flag", lambda x: x.value_counts().index[0]),
                peak_month=("month", lambda x:
                            df.loc[x.index].groupby("month")["fishing_hours"]
                            .sum().idxmax() if len(x) > 0 else 0),
             )
             .reset_index())
    max_fh = agg["total_fishing_hours"].max()
    agg["intensity_norm"] = agg["total_fishing_hours"] / max(max_fh, 1)
    agg["vessel_type"]    = agg["dominant_gear"].map(GFW_GEARTYPE_MAP).fillna("other")
    return agg.sort_values("total_fishing_hours", ascending=False)
