"""
Real AIS Data Loader — All Vessel Types

Normalises raw AIS data from multiple sources into a standard schema
compatible with the activity intelligence pipeline.

Supported sources:
  - NOAA Coast Guard / MarineCadastre  (US waters, all vessel types)
  - INFORE / Piraeus-style dataset      (Greek waters, UUID-based)
  - Danish Maritime Authority (DMA)     (Danish/Baltic waters)
  - Generic CSV                         (any source with mappable columns)

Output schema (one row per AIS ping):
  timestamp   : datetime64[ns] UTC
  mmsi        : str  (MMSI or pseudonymous vessel ID)
  lat         : float64
  lon         : float64
  sog         : float32   knots
  cog         : float32   degrees
  heading     : float32   degrees
  vessel_type : str       internal type key
  nav_status  : int8      ITU nav status code (0-15, -1 if unknown)
  true_activity: str      derived from nav_status where possible
  vessel_name : str       (empty if not available)
  imo         : str
  length_m    : float32
  source      : str       dataset name

ITU vessel type groups → internal keys:
  30          → fishing
  31-32       → tug            (towing)
  33-34       → support_vessel (dredging / diving ops)
  35, 55      → naval          (military / law enforcement)
  36          → sailing
  37          → pleasure_craft
  38-39       → unknown
  40-49       → hsc            (high-speed craft)
  50-54, 58-59→ support_vessel (pilot / SAR / tender / anti-poll / medical)
  60-69       → passenger
  70-79       → cargo
  71          → cargo          (cargo hazardous A)
  79          → cargo
  80-89       → tanker
  90-99       → other

ITU navigational status → true_activity:
  0           → transit        (under way using engine)
  1           → anchored       (at anchor)
  2           → transit        (not under command — still moving)
  3           → transit        (restricted manoeuvrability)
  5           → anchored       (moored)
  7           → fishing
  8           → transit        (under way sailing)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import zipfile
import io

# ── ITU vessel type code → internal type key ──────────────────────────────────

def _build_itu_map() -> dict:
    m = {}
    m[0]  = "unknown"
    m[30] = "fishing"
    for c in [31, 32]:          m[c] = "tug"
    for c in [33, 34]:          m[c] = "support_vessel"
    m[35] = "naval"
    m[36] = "sailing"
    m[37] = "pleasure_craft"
    for c in range(38, 40):     m[c] = "unknown"
    for c in range(40, 50):     m[c] = "hsc"
    for c in [50, 51, 52, 53, 54, 58, 59]:  m[c] = "support_vessel"
    m[55] = "naval"
    for c in [56, 57]:          m[c] = "unknown"
    for c in range(60, 70):     m[c] = "passenger"
    for c in range(70, 80):     m[c] = "cargo"
    for c in range(80, 90):     m[c] = "tanker"
    for c in range(90, 100):    m[c] = "other"
    return m

ITU_VESSEL_TYPE_MAP = _build_itu_map()

# Navigational status → activity
NAV_STATUS_ACTIVITY = {
    0:  "transit",    # under way using engine
    1:  "anchored",   # at anchor
    2:  "transit",    # not under command
    3:  "transit",    # restricted manoeuvrability
    4:  "transit",    # constrained by draught
    5:  "anchored",   # moored
    6:  "anchored",   # aground
    7:  "fishing",
    8:  "transit",    # under way sailing
    11: "transit",    # towing astern
    12: "transit",    # pushing ahead
    14: "transit",    # AIS-SART
}

# Human-readable labels for output tables
VESSEL_TYPE_LABELS = {
    "fishing":        "Fishing",
    "tug":            "Tug / Towing",
    "support_vessel": "Support / SAR / Pilot",
    "naval":          "Naval / Law Enforcement",
    "sailing":        "Sailing Vessel",
    "pleasure_craft": "Pleasure Craft",
    "hsc":            "High-Speed Craft",
    "passenger":      "Passenger",
    "cargo":          "Cargo",
    "tanker":         "Tanker",
    "other":          "Other",
    "unknown":        "Unknown",
}


# ── Normalisers per source ────────────────────────────────────────────────────

def _normalise_noaa(df: pd.DataFrame, source_tag: str = "noaa") -> pd.DataFrame:
    """Normalise NOAA/MarineCadastre AIS CSV."""
    out = pd.DataFrame()
    out["timestamp"]   = pd.to_datetime(df["BaseDateTime"], utc=True, errors="coerce")
    out["mmsi"]        = df["MMSI"].astype(str)
    out["lat"]         = pd.to_numeric(df["LAT"],     errors="coerce").astype("float32")
    out["lon"]         = pd.to_numeric(df["LON"],     errors="coerce").astype("float32")
    out["sog"]         = pd.to_numeric(df["SOG"],     errors="coerce").astype("float32")
    out["cog"]         = pd.to_numeric(df["COG"],     errors="coerce").astype("float32")
    out["heading"]     = pd.to_numeric(df["Heading"], errors="coerce").astype("float32")
    out["nav_status"]  = pd.to_numeric(df.get("Status", pd.Series([-1]*len(df))),
                                        errors="coerce").fillna(-1).astype("int8")
    out["vessel_name"] = df.get("VesselName", "").fillna("").astype(str)
    out["imo"]         = df.get("IMO", "").fillna("").astype(str)
    out["length_m"]    = pd.to_numeric(df.get("Length", pd.Series([np.nan]*len(df))),
                                        errors="coerce").astype("float32")

    vtype_code = pd.to_numeric(df.get("VesselType", pd.Series([0]*len(df))),
                                errors="coerce").fillna(0).astype(int)
    out["vessel_type"]    = vtype_code.map(ITU_VESSEL_TYPE_MAP).fillna("unknown")
    out["true_activity"]  = out["nav_status"].map(NAV_STATUS_ACTIVITY).fillna("unknown")
    out["source"]         = source_tag
    return out


def _normalise_infore(df: pd.DataFrame, source_tag: str = "infore") -> pd.DataFrame:
    """Normalise INFORE / Piraeus-style AIS CSV.
    Columns: t, shipid, lon, lat, heading, course, speed, shiptype, destination
    """
    out = pd.DataFrame()
    out["timestamp"]   = pd.to_datetime(df["t"], utc=True, errors="coerce")
    out["mmsi"]        = df["shipid"].astype(str)
    out["lat"]         = pd.to_numeric(df["lat"],     errors="coerce").astype("float32")
    out["lon"]         = pd.to_numeric(df["lon"],     errors="coerce").astype("float32")
    out["sog"]         = pd.to_numeric(df["speed"],   errors="coerce").astype("float32")
    out["cog"]         = pd.to_numeric(df["course"],  errors="coerce").astype("float32")
    out["heading"]     = pd.to_numeric(df["heading"], errors="coerce").astype("float32")
    out["nav_status"]  = np.int8(-1)
    out["vessel_name"] = ""
    out["imo"]         = ""
    out["length_m"]    = np.float32(np.nan)

    vtype_code = pd.to_numeric(df.get("shiptype", pd.Series([0]*len(df))),
                                errors="coerce").fillna(0).astype(int)
    out["vessel_type"]    = vtype_code.map(ITU_VESSEL_TYPE_MAP).fillna("unknown")
    out["true_activity"]  = "unknown"   # no nav status in this dataset
    out["source"]         = source_tag
    return out


def _normalise_dma(df: pd.DataFrame, source_tag: str = "dma") -> pd.DataFrame:
    """Normalise Danish Maritime Authority AIS CSV.
    Columns: Timestamp, Type of mobile, MMSI, Latitude, Longitude,
             Navigational status, ROT, SOG, COG, Heading, IMO, Callsign,
             Name, Ship type, Cargo type, Width, Length, ...
    """
    out = pd.DataFrame()
    out["timestamp"]   = pd.to_datetime(df["Timestamp"], utc=True, errors="coerce")
    out["mmsi"]        = df["MMSI"].astype(str)
    out["lat"]         = pd.to_numeric(df["Latitude"],  errors="coerce").astype("float32")
    out["lon"]         = pd.to_numeric(df["Longitude"], errors="coerce").astype("float32")
    out["sog"]         = pd.to_numeric(df["SOG"],       errors="coerce").astype("float32")
    out["cog"]         = pd.to_numeric(df["COG"],       errors="coerce").astype("float32")
    out["heading"]     = pd.to_numeric(df["Heading"],   errors="coerce").astype("float32")

    nav_raw = df.get("Navigational status", "")
    nav_map = {
        "Under way using engine": 0, "At anchor": 1, "Not under command": 2,
        "Restricted manoeuverability": 3, "Constrained by draught": 4,
        "Moored": 5, "Aground": 6, "Engaged in fishing": 7,
        "Under way sailing": 8, "undefined": 15,
    }
    out["nav_status"]  = nav_raw.map(nav_map).fillna(-1).astype("int8")
    out["vessel_name"] = df.get("Name", "").fillna("").astype(str)
    out["imo"]         = df.get("IMO", "").fillna("").astype(str)
    out["length_m"]    = pd.to_numeric(df.get("Length", pd.Series([np.nan]*len(df))),
                                        errors="coerce").astype("float32")

    vtype_code = pd.to_numeric(df.get("Ship type", pd.Series([0]*len(df))),
                                errors="coerce").fillna(0).astype(int)
    out["vessel_type"]    = vtype_code.map(ITU_VESSEL_TYPE_MAP).fillna("unknown")
    out["true_activity"]  = out["nav_status"].map(NAV_STATUS_ACTIVITY).fillna("unknown")
    out["source"]         = source_tag
    return out


# ── Source auto-detection ─────────────────────────────────────────────────────

def _detect_source(cols: list) -> str:
    cols_l = [c.lower() for c in cols]
    if "basedatetime" in cols_l:
        return "noaa"
    if "shipid" in cols_l or "t" in cols_l and "shiptype" in cols_l:
        return "infore"
    if "navigational status" in cols_l or "ship type" in cols_l:
        return "dma"
    return "generic"


def _normalise_generic(df: pd.DataFrame, source_tag: str = "generic") -> pd.DataFrame:
    """Best-effort normalisation for unknown CSV schemas."""
    col_map = {}
    rename = {
        "lat": ["lat", "latitude", "y"],
        "lon": ["lon", "lng", "longitude", "x"],
        "sog": ["sog", "speed", "speed_over_ground"],
        "cog": ["cog", "course", "course_over_ground"],
        "heading": ["heading", "hdg", "true_heading"],
        "mmsi": ["mmsi", "shipid", "vessel_id", "id"],
        "timestamp": ["timestamp", "basedatetime", "datetime", "time", "t"],
        "vessel_type": ["vesseltype", "shiptype", "ship_type", "vessel_type"],
        "nav_status": ["status", "nav_status", "navigational status", "navstat"],
    }
    cols_l = {c.lower(): c for c in df.columns}
    for target, candidates in rename.items():
        for cand in candidates:
            if cand in cols_l:
                col_map[cols_l[cand]] = target
                break

    df2 = df.rename(columns=col_map)

    out = pd.DataFrame()
    out["timestamp"]  = pd.to_datetime(df2.get("timestamp", pd.NaT), utc=True, errors="coerce")
    out["mmsi"]       = df2.get("mmsi", pd.Series([""] * len(df2))).astype(str)
    out["lat"]        = pd.to_numeric(df2.get("lat", np.nan), errors="coerce").astype("float32")
    out["lon"]        = pd.to_numeric(df2.get("lon", np.nan), errors="coerce").astype("float32")
    out["sog"]        = pd.to_numeric(df2.get("sog", np.nan), errors="coerce").astype("float32")
    out["cog"]        = pd.to_numeric(df2.get("cog", np.nan), errors="coerce").astype("float32")
    out["heading"]    = pd.to_numeric(df2.get("heading", np.nan), errors="coerce").astype("float32")
    out["nav_status"] = pd.to_numeric(df2.get("nav_status", -1), errors="coerce").fillna(-1).astype("int8")
    out["vessel_name"]= ""
    out["imo"]        = ""
    out["length_m"]   = np.float32(np.nan)

    if "vessel_type" in df2.columns:
        vtype_code = pd.to_numeric(df2["vessel_type"], errors="coerce").fillna(0).astype(int)
        out["vessel_type"] = vtype_code.map(ITU_VESSEL_TYPE_MAP).fillna("unknown")
    else:
        out["vessel_type"] = "unknown"

    out["true_activity"] = out["nav_status"].map(NAV_STATUS_ACTIVITY).fillna("unknown")
    out["source"]        = source_tag
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def load_ais_file(path: str | Path, source: str = "auto",
                  max_rows: int | None = None,
                  bbox: tuple | None = None) -> pd.DataFrame:
    """
    Load and normalise an AIS CSV or ZIP file.

    Parameters
    ----------
    path     : path to .csv or .zip file
    source   : "noaa" | "infore" | "dma" | "generic" | "auto"
    max_rows : limit number of rows read (useful for large files)
    bbox     : (lon_min, lat_min, lon_max, lat_max) spatial filter

    Returns
    -------
    Normalised DataFrame with standard AIS schema.
    """
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csv_names:
                raise ValueError(f"No CSV files found inside {path}")
            with zf.open(csv_names[0]) as f:
                raw = pd.read_csv(f, nrows=max_rows, low_memory=False)
    else:
        raw = pd.read_csv(path, nrows=max_rows, low_memory=False)

    if source == "auto":
        source = _detect_source(list(raw.columns))

    normalisers = {
        "noaa":    _normalise_noaa,
        "infore":  _normalise_infore,
        "dma":     _normalise_dma,
        "generic": _normalise_generic,
    }
    df = normalisers.get(source, _normalise_generic)(raw, source_tag=source)

    # Drop invalid rows
    df = df.dropna(subset=["lat", "lon", "sog", "timestamp"])
    df = df[(df["lat"].between(-90, 90)) & (df["lon"].between(-180, 180))]
    df = df[(df["sog"] >= 0) & (df["sog"] < 120)]

    # Spatial filter
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        df = df[(df["lon"].between(lon_min, lon_max)) &
                (df["lat"].between(lat_min, lat_max))]

    df = df.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)
    return df


def fleet_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-vessel summary from a normalised AIS DataFrame."""
    rows = []
    for mmsi, g in df.groupby("mmsi"):
        g = g.sort_values("timestamp")
        rows.append({
            "mmsi":         mmsi,
            "vessel_name":  g["vessel_name"].iloc[0],
            "vessel_type":  g["vessel_type"].mode().iloc[0],
            "n_pings":      len(g),
            "sog_mean":     float(g["sog"].mean()),
            "sog_max":      float(g["sog"].max()),
            "true_activity_mode": g["true_activity"].mode().iloc[0],
            "lat_min": float(g["lat"].min()), "lat_max": float(g["lat"].max()),
            "lon_min": float(g["lon"].min()), "lon_max": float(g["lon"].max()),
            "imo":     g["imo"].iloc[0],
            "length_m": float(g["length_m"].median()) if g["length_m"].notna().any() else np.nan,
            "source":   g["source"].iloc[0],
        })
    return pd.DataFrame(rows)


def type_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Vessel type distribution with human-readable labels."""
    counts = df.groupby("vessel_type").agg(
        n_pings   = ("mmsi", "count"),
        n_vessels = ("mmsi", "nunique"),
    ).reset_index()
    counts["label"] = counts["vessel_type"].map(VESSEL_TYPE_LABELS).fillna(counts["vessel_type"])
    counts = counts.sort_values("n_pings", ascending=False)
    counts["pct_pings"] = counts["n_pings"] / counts["n_pings"].sum()
    return counts
