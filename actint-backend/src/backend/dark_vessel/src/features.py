"""
Feature engineering for AIS tracks.

Two modes:
  1. compute_vessel_features()  – one row per MMSI (voyage-level)
  2. compute_segment_features() – one row per sliding window segment (preferred for classification)
"""

import numpy as np
import pandas as pd
from scipy.stats import circstd
from math import radians, cos, sin, asin, sqrt
from joblib import Parallel, delayed
import multiprocessing

N_CORES = multiprocessing.cpu_count()


# ---------------------------------------------------------------------------
# Haversine distance (nm)
# ---------------------------------------------------------------------------

def haversine_nm(lat1, lon1, lat2, lon2):
    R = 3440.065  # Earth radius in nm
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(max(0, a)))


def haversine_series(df: pd.DataFrame) -> pd.Series:
    """Row-wise haversine using shifted lat/lon within each vessel group."""
    lats = df["lat"].values
    lons = df["lon"].values
    prev_lat = np.roll(lats, 1)
    prev_lon = np.roll(lons, 1)
    dists = np.zeros(len(df))
    for i in range(1, len(df)):
        dists[i] = haversine_nm(prev_lat[i], prev_lon[i], lats[i], lons[i])
    return pd.Series(dists, index=df.index)


# ---------------------------------------------------------------------------
# Per-vessel feature extraction
# ---------------------------------------------------------------------------

def _circular_std(angles):
    """Circular standard deviation for heading/COG."""
    rad = np.radians(angles)
    sin_m = np.sin(rad).mean()
    cos_m = np.cos(rad).mean()
    R = np.sqrt(sin_m**2 + cos_m**2)
    return float(np.degrees(np.sqrt(-2 * np.log(np.clip(R, 1e-9, 1.0)))))


def _pct_slow(sog: np.ndarray, threshold=5.0) -> float:
    return float(np.mean(sog < threshold))


def _pct_very_slow(sog: np.ndarray, threshold=2.0) -> float:
    return float(np.mean(sog < threshold))


def _turning_rate(cog: np.ndarray) -> np.ndarray:
    diff = np.diff(cog)
    diff = (diff + 180) % 360 - 180  # wrap to [-180, 180]
    return np.abs(diff)


def _loiter_index(lats, lons):
    """Convex hull area / total path length – small = loitering."""
    if len(lats) < 4:
        return 0.0
    from shapely.geometry import MultiPoint, LineString
    try:
        hull_area = MultiPoint(list(zip(lons, lats))).convex_hull.area
        path_len  = sum(
            haversine_nm(lats[i], lons[i], lats[i+1], lons[i+1])
            for i in range(len(lats)-1)
        )
        return hull_area / max(path_len**2, 1e-9)
    except Exception:
        return 0.0


def _zig_zag_score(cog: np.ndarray) -> float:
    """Fraction of pings with a heading change > 30°."""
    tr = _turning_rate(cog)
    return float(np.mean(tr > 30)) if len(tr) > 0 else 0.0


def _proximity_to_points(lat, lon, points: list) -> float:
    """Minimum distance (nm) to a list of {lat, lon} dicts."""
    if not points:
        return 9999.0
    dists = [haversine_nm(lat, lon, p["lat"], p["lon"]) for p in points]
    return float(min(dists))


def compute_vessel_features(df: pd.DataFrame, region_key: str | None = None) -> pd.DataFrame:
    """
    Compute per-vessel aggregate features.

    Returns one row per MMSI with ~30 features.
    """
    from .regions import REGIONS, nearest_port, nearest_fishing_ground

    rows = []
    for mmsi, grp in df.groupby("mmsi"):
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        sog   = grp["sog"].values
        cog   = grp["cog"].values
        lats  = grp["lat"].values
        lons  = grp["lon"].values
        n     = len(grp)

        # Duration
        t_span_h = (grp["timestamp"].iloc[-1] - grp["timestamp"].iloc[0]).total_seconds() / 3600

        # Speed statistics
        sog_mean   = float(np.mean(sog))
        sog_std    = float(np.std(sog))
        sog_max    = float(np.max(sog))
        pct_slow   = _pct_slow(sog, 5.0)
        pct_vslow  = _pct_very_slow(sog, 2.0)
        pct_fast   = float(np.mean(sog > 14))

        # Heading / turning
        cog_std    = _circular_std(cog)
        zig_zag    = _zig_zag_score(cog)
        tr         = _turning_rate(cog)
        mean_tr    = float(np.mean(tr)) if len(tr) > 0 else 0.0
        max_tr     = float(np.max(tr))  if len(tr) > 0 else 0.0

        # Spatial
        loiter_idx = _loiter_index(lats, lons)
        centroid_lat = float(np.mean(lats))
        centroid_lon = float(np.mean(lons))
        lat_range    = float(lats.max() - lats.min())
        lon_range    = float(lons.max() - lons.min())
        total_dist_nm = float(haversine_series(grp).sum())
        bbox_area    = lat_range * lon_range

        # Nav status
        nav = grp["nav_status"].values
        pct_fishing_status = float(np.mean(nav == 7))
        pct_anchored_status = float(np.mean(nav == 1))

        # AIS gaps (dark detection)
        grp2 = grp.copy()
        grp2["dt_min"] = grp2["timestamp"].diff().dt.total_seconds().fillna(0) / 60
        n_dark_gaps = int(np.sum(grp2["dt_min"] > 60))   # gaps > 1h
        max_dark_gap_h = float(grp2["dt_min"].max() / 60)
        pct_dark = float(grp["ais_on"].eq(False).mean()) if "ais_on" in grp.columns else 0.0

        # Physical characteristics
        length = int(grp["length"].iloc[0])
        draught = float(grp["draught"].iloc[0])

        # Proximity features (if region context available)
        dist_to_port_nm   = 9999.0
        dist_to_fishing_nm = 9999.0
        if region_key and region_key in REGIONS:
            region = REGIONS[region_key]
            if "primary_ports" in region:
                dist_to_port_nm = _proximity_to_points(
                    centroid_lat, centroid_lon, region["primary_ports"])
            if "fishing_grounds" in region:
                dist_to_fishing_nm = _proximity_to_points(
                    centroid_lat, centroid_lon, region["fishing_grounds"])

        # Ground truth (only available in simulation)
        true_activity = grp["true_activity"].mode().iloc[0] if "true_activity" in grp.columns else None
        vessel_type_key = grp["vessel_type_key"].iloc[0] if "vessel_type_key" in grp.columns else None
        flag  = grp["flag"].iloc[0]
        name  = grp["name"].iloc[0]

        rows.append({
            "mmsi": mmsi,
            "name": name,
            "flag": flag,
            "vessel_type_key": vessel_type_key,
            "true_activity": true_activity,
            # Speed
            "sog_mean": sog_mean,
            "sog_std": sog_std,
            "sog_max": sog_max,
            "pct_slow": pct_slow,
            "pct_vslow": pct_vslow,
            "pct_fast": pct_fast,
            # Heading
            "cog_std": cog_std,
            "zig_zag": zig_zag,
            "mean_turning_rate": mean_tr,
            "max_turning_rate": max_tr,
            # Spatial
            "loiter_index": loiter_idx,
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
            "lat_range": lat_range,
            "lon_range": lon_range,
            "total_dist_nm": total_dist_nm,
            "bbox_area": bbox_area,
            "t_span_h": t_span_h,
            # Nav status
            "pct_fishing_status": pct_fishing_status,
            "pct_anchored_status": pct_anchored_status,
            # Dark
            "n_dark_gaps": n_dark_gaps,
            "max_dark_gap_h": max_dark_gap_h,
            "pct_dark": pct_dark,
            # Physical
            "length": length,
            "draught": draught,
            # Proximity
            "dist_to_port_nm": dist_to_port_nm,
            "dist_to_fishing_nm": dist_to_fishing_nm,
            # Counts
            "n_pings": n,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Segment-level features (sliding window – preferred for classification)
# ---------------------------------------------------------------------------

def _compute_segments_one_vessel(mmsi, grp, region_key, window_size, step_size,
                                  ports, fishing_grounds):
    """Compute segment features for a single vessel — called in parallel."""
    grp = grp.sort_values("timestamp").reset_index(drop=True)
    length  = int(grp["length"].iloc[0]) if "length" in grp.columns else 0
    draught = float(grp["draught"].iloc[0]) if "draught" in grp.columns else 0.0
    flag    = grp["flag"].iloc[0] if "flag" in grp.columns else ""
    name    = grp["name"].iloc[0] if "name" in grp.columns else ""
    vtype   = grp["vessel_type_key"].iloc[0] if "vessel_type_key" in grp.columns else "unknown"

    n = len(grp)
    rows = []
    for start in range(0, n - window_size + 1, step_size):
        win = grp.iloc[start: start + window_size]
        sog  = win["sog"].values.astype(float)
        cog  = win["cog"].values.astype(float) if "cog" in win else np.zeros(len(win))
        lats = win["lat"].values.astype(float)
        lons = win["lon"].values.astype(float)
        nav  = win["nav_status"].values.astype(float) if "nav_status" in win else np.full(len(win), -1)

        if "true_activity" in win.columns:
            true_activity = win["true_activity"].mode().iloc[0]
        else:
            true_activity = None

        t_span_h = (win["timestamp"].iloc[-1] - win["timestamp"].iloc[0]).total_seconds() / 3600
        if t_span_h < 0.01:
            continue

        sog_mean  = float(np.mean(sog));  sog_std = float(np.std(sog))
        sog_max   = float(np.max(sog))
        pct_slow  = _pct_slow(sog);        pct_vslow = _pct_very_slow(sog)
        pct_fast  = float(np.mean(sog > 14))

        cog_std   = _circular_std(cog)
        zig_zag   = _zig_zag_score(cog)
        tr        = _turning_rate(cog)
        mean_tr   = float(np.mean(tr)) if len(tr) > 0 else 0.0
        max_tr    = float(np.max(tr))  if len(tr) > 0 else 0.0

        loiter_idx   = _loiter_index(lats, lons)
        centroid_lat = float(np.mean(lats));  centroid_lon = float(np.mean(lons))
        lat_range    = float(lats.max() - lats.min())
        lon_range    = float(lons.max() - lons.min())
        total_dist   = sum(
            haversine_nm(lats[i-1], lons[i-1], lats[i], lons[i])
            for i in range(1, len(lats))
        )
        bbox_area    = lat_range * lon_range

        pct_fishing_status  = float(np.mean(nav == 7))
        pct_anchored_status = float(np.mean(np.isin(nav, [1, 5])))

        win2 = win.copy()
        win2["dt_min"] = win2["timestamp"].diff().dt.total_seconds().fillna(0) / 60
        n_dark_gaps    = int(np.sum(win2["dt_min"] > 60))
        max_dark_gap_h = float(win2["dt_min"].max() / 60)
        pct_dark       = float(win["ais_on"].eq(False).mean()) if "ais_on" in win.columns else 0.0

        dist_to_port_nm    = 9999.0
        dist_to_fishing_nm = 9999.0
        if ports:
            dist_to_port_nm = min(_proximity_to_points(centroid_lat, centroid_lon, ports),
                                  dist_to_port_nm)
        if fishing_grounds:
            dist_to_fishing_nm = min(_proximity_to_points(centroid_lat, centroid_lon, fishing_grounds),
                                     dist_to_fishing_nm)

        rows.append({
            "mmsi": mmsi, "name": name, "flag": flag, "vessel_type_key": vtype,
            "true_activity": true_activity,
            "segment_start": win["timestamp"].iloc[0],
            "centroid_lat": centroid_lat, "centroid_lon": centroid_lon,
            "sog_mean": sog_mean, "sog_std": sog_std, "sog_max": sog_max,
            "pct_slow": pct_slow, "pct_vslow": pct_vslow, "pct_fast": pct_fast,
            "cog_std": cog_std, "zig_zag": zig_zag,
            "mean_turning_rate": mean_tr, "max_turning_rate": max_tr,
            "loiter_index": loiter_idx,
            "lat_range": lat_range, "lon_range": lon_range,
            "total_dist_nm": total_dist, "bbox_area": bbox_area, "t_span_h": t_span_h,
            "pct_fishing_status": pct_fishing_status,
            "pct_anchored_status": pct_anchored_status,
            "n_dark_gaps": n_dark_gaps, "max_dark_gap_h": max_dark_gap_h, "pct_dark": pct_dark,
            "length": length, "draught": draught,
            "dist_to_port_nm": dist_to_port_nm, "dist_to_fishing_nm": dist_to_fishing_nm,
            "n_pings": window_size,
        })
    return rows


def compute_segment_features(
    df: pd.DataFrame,
    region_key: str | None = None,
    window_size: int = 20,
    step_size: int = 10,
    n_jobs: int = -1,
    geo_augment: bool = True,
) -> pd.DataFrame:
    """
    Slide a window of `window_size` pings over each vessel's track.
    Return one feature row per window with a dominant-activity label.
    Parallelised across vessels using all CPU cores.

    If geo_augment=True (default), appends GFW fishing effort density,
    shipping lane proximity, and gear-depth fitness columns using
    GeoFeatureAugmenter.  Requires the GFW effort cache to be built on
    first call (~30 s); subsequent calls load from disk instantly.
    """
    from .regions import REGIONS, nearest_port, nearest_fishing_ground

    ports = fishing_grounds = []
    if region_key and region_key in REGIONS:
        region = REGIONS[region_key]
        ports          = region.get("primary_ports", [])
        fishing_grounds= region.get("fishing_grounds", [])

    groups = [(mmsi, grp.copy()) for mmsi, grp in df.groupby("mmsi")]

    all_rows = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
        delayed(_compute_segments_one_vessel)(
            mmsi, grp, region_key, window_size, step_size, ports, fishing_grounds
        )
        for mmsi, grp in groups
    )

    rows = [r for sub in all_rows for r in sub]
    result = pd.DataFrame(rows)

    if geo_augment and not result.empty:
        from .geo_features import GeoFeatureAugmenter
        aug = GeoFeatureAugmenter(fetch_depth=False)
        result = aug.augment(result, lat_col="centroid_lat", lon_col="centroid_lon")

    return result


def _compute_segment_features_serial(
    df: pd.DataFrame,
    region_key: str | None = None,
    window_size: int = 20,
    step_size: int = 10,
) -> pd.DataFrame:
    """Serial fallback — kept for reference."""
    from .regions import REGIONS, nearest_port, nearest_fishing_ground

    rows = []
    for mmsi, grp in df.groupby("mmsi"):
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        # Physical constants for this vessel
        length  = int(grp["length"].iloc[0])
        draught = float(grp["draught"].iloc[0])
        flag    = grp["flag"].iloc[0]
        name    = grp["name"].iloc[0]
        vtype   = grp["vessel_type_key"].iloc[0] if "vessel_type_key" in grp.columns else "unknown"

        n = len(grp)
        for start in range(0, n - window_size + 1, step_size):
            win = grp.iloc[start: start + window_size]
            sog = win["sog"].values
            cog = win["cog"].values
            lats = win["lat"].values
            lons = win["lon"].values
            nav  = win["nav_status"].values

            # Dominant activity for this window
            if "true_activity" in win.columns:
                true_activity = win["true_activity"].mode().iloc[0]
            else:
                true_activity = None

            # Time
            t_span_h = (win["timestamp"].iloc[-1] - win["timestamp"].iloc[0]).total_seconds() / 3600
            if t_span_h < 0.01:
                continue

            # Speed
            sog_mean  = float(np.mean(sog))
            sog_std   = float(np.std(sog))
            sog_max   = float(np.max(sog))
            pct_slow  = _pct_slow(sog)
            pct_vslow = _pct_very_slow(sog)
            pct_fast  = float(np.mean(sog > 14))

            # Heading
            cog_std  = _circular_std(cog)
            zig_zag  = _zig_zag_score(cog)
            tr       = _turning_rate(cog)
            mean_tr  = float(np.mean(tr)) if len(tr) > 0 else 0.0
            max_tr   = float(np.max(tr))  if len(tr) > 0 else 0.0

            # Spatial
            loiter_idx   = _loiter_index(lats, lons)
            centroid_lat = float(np.mean(lats))
            centroid_lon = float(np.mean(lons))
            lat_range    = float(lats.max() - lats.min())
            lon_range    = float(lons.max() - lons.min())
            total_dist   = float(haversine_series(win).sum())
            bbox_area    = lat_range * lon_range

            # Nav status
            pct_fishing_status  = float(np.mean(nav == 7))
            pct_anchored_status = float(np.mean(nav == 1))

            # Dark
            win2 = win.copy()
            win2["dt_min"] = win2["timestamp"].diff().dt.total_seconds().fillna(0) / 60
            n_dark_gaps   = int(np.sum(win2["dt_min"] > 60))
            max_dark_gap_h = float(win2["dt_min"].max() / 60)
            pct_dark      = float(win["ais_on"].eq(False).mean()) if "ais_on" in win.columns else 0.0

            # Proximity
            dist_to_port_nm    = 9999.0
            dist_to_fishing_nm = 9999.0
            if region_key and region_key in REGIONS:
                region = REGIONS[region_key]
                if "primary_ports" in region:
                    dist_to_port_nm = _proximity_to_points(
                        centroid_lat, centroid_lon, region["primary_ports"])
                if "fishing_grounds" in region:
                    dist_to_fishing_nm = _proximity_to_points(
                        centroid_lat, centroid_lon, region["fishing_grounds"])

            rows.append({
                "mmsi": mmsi,
                "name": name,
                "flag": flag,
                "vessel_type_key": vtype,
                "true_activity": true_activity,
                "segment_start": win["timestamp"].iloc[0],
                "centroid_lat": centroid_lat,
                "centroid_lon": centroid_lon,
                # Speed
                "sog_mean": sog_mean,
                "sog_std": sog_std,
                "sog_max": sog_max,
                "pct_slow": pct_slow,
                "pct_vslow": pct_vslow,
                "pct_fast": pct_fast,
                # Heading
                "cog_std": cog_std,
                "zig_zag": zig_zag,
                "mean_turning_rate": mean_tr,
                "max_turning_rate": max_tr,
                # Spatial
                "loiter_index": loiter_idx,
                "lat_range": lat_range,
                "lon_range": lon_range,
                "total_dist_nm": total_dist,
                "bbox_area": bbox_area,
                "t_span_h": t_span_h,
                # Nav
                "pct_fishing_status": pct_fishing_status,
                "pct_anchored_status": pct_anchored_status,
                # Dark
                "n_dark_gaps": n_dark_gaps,
                "max_dark_gap_h": max_dark_gap_h,
                "pct_dark": pct_dark,
                # Physical
                "length": length,
                "draught": draught,
                # Proximity
                "dist_to_port_nm": dist_to_port_nm,
                "dist_to_fishing_nm": dist_to_fishing_nm,
                "n_pings": window_size,
            })

    return pd.DataFrame(rows)
