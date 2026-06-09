"""
Partial Track Activity & Type Classifier

Classifies vessel activity from ANY number of observations (N ≥ 1).

Designed for real-world multi-sensor scenarios where custody is brief:
  • AIS cut out — only 3–10 pings before silence
  • LEO EO satellite — 1–2 observations per pass (~90 min orbit)
  • Maritime patrol aircraft — brief radar contact (seconds–minutes)
  • SAR image — single snapshot with position, heading, rough speed
  • Fused multi-source — combine pings from different sensors

Architecture:
  • Feature vector defined for N = 1 .. ∞; NaN where insufficient data
  • XGBoost handles NaN natively (learned split directions per feature)
  • Confidence score calibrated to N, sensor quality, feature completeness
  • Separate models for activity (6 classes) and vessel type (12 classes)
  • Trained on BOTH synthetic tracks (ground truth labels) AND real AIS
    resampled to varying track lengths (N = 1, 3, 5, 10, 20, 50)

Sensor types and capabilities:
  ais          — position ±10m, SOG ±0.1kn, heading ±1°, MMSI (full metadata)
  ais_aircraft — same as AIS, collected by aircraft receiver
  radar        — position ±100–500m, SOG ±1kn, heading ±5°, no MMSI
  sar          — position ±30m, Doppler SOG ±0.5kn, heading ±5°, no MMSI
  eo           — position ±50m, no SOG (unless multi-frame), no MMSI
  rfdf         — bearing only, rough range; no precise position
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import joblib
from joblib import Parallel, delayed
import multiprocessing

from ..util.gpu_utils import make_activity_classifier, make_type_classifier, N_CORES
from ..real_data_helpers.real_ais_loader import NAV_STATUS_ACTIVITY

# ── Sensor metadata ──────────────────────────────────────────────────────────

SENSOR_TYPES = {
    "ais":          {"enc": 0, "pos_acc_m": 10,  "sog_acc_kn": 0.1, "hdg_acc_deg": 1,  "has_id": True,  "quality": 1.00},
    "ais_aircraft": {"enc": 1, "pos_acc_m": 10,  "sog_acc_kn": 0.1, "hdg_acc_deg": 1,  "has_id": True,  "quality": 0.90},
    "radar":        {"enc": 2, "pos_acc_m": 300, "sog_acc_kn": 1.0, "hdg_acc_deg": 5,  "has_id": False, "quality": 0.65},
    "sar":          {"enc": 3, "pos_acc_m": 30,  "sog_acc_kn": 0.5, "hdg_acc_deg": 5,  "has_id": False, "quality": 0.60},
    "eo":           {"enc": 4, "pos_acc_m": 50,  "sog_acc_kn": None,"hdg_acc_deg": 10, "has_id": False, "quality": 0.40},
    "rfdf":         {"enc": 5, "pos_acc_m": 5000,"sog_acc_kn": None,"hdg_acc_deg": None,"has_id": False, "quality": 0.20},
}

# ── Unified vessel type taxonomy (covers simulator + real AIS ITU codes) ─────

UNIFIED_VESSEL_TYPES = [
    "fishing",       # 0 — all fishing gear types
    "cargo",         # 1 — cargo / container / bulk carrier
    "tanker",        # 2 — oil, chemical, LNG tankers
    "passenger",     # 3 — passenger ferries, cruise
    "tug",           # 4 — tugs, towing
    "naval",         # 5 — military, law enforcement, coast guard
    "support_vessel",# 6 — SAR, pilot, anchor handler, platform supply
    "sailing",       # 7 — sailing vessels
    "pleasure_craft",# 8 — recreational motorboats
    "hsc",           # 9 — high-speed craft, ferry
    "other",         # 10 — dredger, diving, unclassified
    "unknown",       # 11 — no type information
]
VT_ENC = {vt: i for i, vt in enumerate(UNIFIED_VESSEL_TYPES)}

# Map simulator vessel_type_key → unified type
SIMULATOR_TO_UNIFIED = {
    "trawler":       "fishing",
    "longliner":     "fishing",
    "purse_seiner":  "fishing",
    "cargo":         "cargo",
    "bulk_carrier":  "cargo",
    "tanker":        "tanker",
    "naval":         "naval",
    "support_vessel":"support_vessel",
}

# Map real AIS loader vessel_type → unified type (already mostly aligned)
LOADER_TO_UNIFIED = {
    "fishing":        "fishing",
    "cargo":          "cargo",
    "tanker":         "tanker",
    "passenger":      "passenger",
    "tug":            "tug",
    "naval":          "naval",
    "support_vessel": "support_vessel",
    "sailing":        "sailing",
    "pleasure_craft": "pleasure_craft",
    "hsc":            "hsc",
    "other":          "other",
    "unknown":        "unknown",
}

# ── Activity labels ───────────────────────────────────────────────────────────

ACTIVITY_LABELS = ["fishing", "transit", "anchored", "loiter", "sts", "port"]
ACT_ENC         = {a: i for i, a in enumerate(ACTIVITY_LABELS)}

# ── Feature names ─────────────────────────────────────────────────────────────

PARTIAL_FEATURES = [
    # ── Observation metadata (always present) ──
    "n_obs",           # number of pings
    "obs_span_min",    # time span in minutes
    "sensor_enc",      # sensor type code
    "sensor_quality",  # sensor reliability [0,1]
    # ── Kinematics — always computable if SOG/COG provided ──
    "sog_mean",
    "sog_std",
    "sog_max",
    "sog_min",
    "heading_mean",    # circular mean heading
    "heading_var",     # circular variance
    # ── Physical attributes ──
    "length_m",        # vessel length (NaN if unknown)
    "vessel_type_enc", # unified type code (-1 if unknown)
    # ── Position context ──
    "centroid_lat",
    "centroid_lon",
    "dist_to_port_nm",
    "dist_to_fishing_nm",
    # ── Time context ──
    "hour_sin",        # sin(2π * hour / 24)
    "hour_cos",
    "is_night",        # 0/1
    # ── 2+ pings: dynamics ──
    "acceleration",    # ΔSoG / Δt  (NaN if n<2)
    "displacement_nm", # straight-line distance (NaN if n<2)
    "mean_heading_change",  # mean |ΔCOG| per step (NaN if n<2)
    "max_heading_change",
    # ── 4+ pings: motion pattern ──
    "pct_slow",        # % pings SOG < 1 kn  (NaN if n<4)
    "pct_vslow",       # % pings SOG < 0.3 kn
    "pct_fast",        # % pings SOG > 14 kn
    "sog_trend",       # linear regression slope of SOG vs time
    # ── 6+ pings: track geometry ──
    "net_to_gross",    # straight-line / path-length (1=pure transit)
    "zig_zag",         # heading reversal count / n_obs  (NaN if n<6)
    "cog_std",         # circular std of heading  (NaN if n<6)
    # ── 10+ pings: spatial pattern ──
    "loiter_index",    # convex_hull_area / path_length²  (NaN if n<10)
    "bbox_area",       # lat_range * lon_range  (NaN if n<10)
    "lat_range",
    "lon_range",
    "mean_turn_rate",  # mean |dCOG/dt|  (NaN if n<10)
    # ── AIS-specific: gap indicators ──
    "n_gaps_10min",    # AIS gaps > 10 min  (0 for non-AIS)
    "max_gap_min",     # largest gap in minutes (NaN if n<2)
    # ── Nav status summary ──
    "pct_fishing_status",  # fraction with nav_status==7
    "pct_anchored_status", # fraction with nav_status in {1,5}
    # ── Geo-contextual priors (from GeoFeatureAugmenter; NaN if not augmented) ──
    "gfw_effort",      # GFW fishing effort density [0,1] at centroid
    "lane_proximity",  # proximity to major shipping lanes [0,1]
    "gear_depth_fit",  # bathymetric depth suitability for fishing gear [0,1]
]

N_PARTIAL_FEATURES = len(PARTIAL_FEATURES)


# ── Haversine helper ──────────────────────────────────────────────────────────

def _hav_nm(lat1, lon1, lat2, lon2) -> float:
    R = 3440.065
    φ1, φ2 = np.radians(lat1), np.radians(lat2)
    Δφ = np.radians(lat2 - lat1)
    Δλ = np.radians(lon2 - lon1)
    a = np.sin(Δφ / 2) ** 2 + np.cos(φ1) * np.cos(φ2) * np.sin(Δλ / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _circular_mean(angles_deg: np.ndarray) -> float:
    r = np.radians(angles_deg)
    return float(np.degrees(np.arctan2(np.nanmean(np.sin(r)), np.nanmean(np.cos(r)))) % 360)


def _circular_var(angles_deg: np.ndarray) -> float:
    r = np.radians(angles_deg)
    R = np.sqrt(np.nanmean(np.sin(r)) ** 2 + np.nanmean(np.cos(r)) ** 2)
    return float(1 - R)  # 0 = all same direction, 1 = uniform


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ── Core feature extractor ────────────────────────────────────────────────────

def extract_partial_features(
    pings: pd.DataFrame | List[Dict[str, Any]],
    sensor_type: str = "ais",
    reference_points: Dict[str, List[Dict]] | None = None,
) -> np.ndarray:
    """
    Extract the PARTIAL_FEATURES vector from 1..N observations.

    Parameters
    ----------
    pings : DataFrame or list of dicts with keys:
              timestamp (datetime or str), lat, lon,
              sog (knots, optional), cog (degrees, optional),
              heading (degrees, optional),
              nav_status (int, optional),
              vessel_type (str, optional),
              length_m (float, optional)
    sensor_type : "ais" | "ais_aircraft" | "radar" | "sar" | "eo" | "rfdf"
    reference_points : dict with optional keys:
              "ports"          : list of {"lat":..,"lon":..}
              "fishing_grounds": list of {"lat":..,"lon":..}

    Returns
    -------
    np.ndarray of shape (N_PARTIAL_FEATURES,) with NaN where unavailable.
    """
    if not isinstance(pings, pd.DataFrame):
        pings = pd.DataFrame(pings)

    n = len(pings)
    NaN = np.nan
    f   = {k: NaN for k in PARTIAL_FEATURES}

    if n == 0:
        return np.array([f[k] for k in PARTIAL_FEATURES])

    # ── Sensor metadata ──
    smeta = SENSOR_TYPES.get(sensor_type, SENSOR_TYPES["ais"])
    f["sensor_enc"]     = float(smeta["enc"])
    f["sensor_quality"] = float(smeta["quality"])
    f["n_obs"]          = float(n)

    # ── Timestamps ──
    if "timestamp" in pings.columns:
        try:
            ts = pd.to_datetime(pings["timestamp"], utc=True).sort_values()
            pings = pings.copy()
            pings["_ts"] = ts
            pings = pings.sort_values("_ts").reset_index(drop=True)
            t0, t1 = pings["_ts"].iloc[0], pings["_ts"].iloc[-1]
            span_min = (t1 - t0).total_seconds() / 60
            f["obs_span_min"] = float(span_min)
            # Time of day from first ping
            hour = t0.hour + t0.minute / 60
            f["hour_sin"] = float(np.sin(2 * np.pi * hour / 24))
            f["hour_cos"] = float(np.cos(2 * np.pi * hour / 24))
            f["is_night"] = float(hour < 6 or hour > 20)
        except Exception:
            f["obs_span_min"] = 0.0

    # ── Positions ──
    lats = pings["lat"].values.astype(float) if "lat" in pings else np.array([NaN])
    lons = pings["lon"].values.astype(float) if "lon" in pings else np.array([NaN])
    f["centroid_lat"] = float(np.nanmean(lats))
    f["centroid_lon"] = float(np.nanmean(lons))

    # ── Kinematics ──
    sog_col = "sog" if "sog" in pings else None
    cog_col = "cog" if "cog" in pings else ("heading" if "heading" in pings else None)

    sog = pings[sog_col].values.astype(float) if sog_col else np.full(n, NaN)
    cog = pings[cog_col].values.astype(float) if cog_col else np.full(n, NaN)

    # Replace AIS sentinel values
    sog = np.where(sog > 102, NaN, sog)   # 102.3 = not available in AIS
    cog = np.where(cog >= 360, NaN, cog)  # 360 = not available

    if not np.all(np.isnan(sog)):
        f["sog_mean"] = float(np.nanmean(sog))
        f["sog_std"]  = float(np.nanstd(sog))
        f["sog_max"]  = float(np.nanmax(sog))
        f["sog_min"]  = float(np.nanmin(sog))

    valid_cog = cog[~np.isnan(cog)]
    if len(valid_cog) > 0:
        f["heading_mean"] = _circular_mean(valid_cog)
        f["heading_var"]  = _circular_var(valid_cog)

    # ── Physical attributes ──
    if "length_m" in pings.columns:
        lm = pd.to_numeric(pings["length_m"], errors="coerce").dropna()
        if len(lm) > 0:
            f["length_m"] = float(lm.median())

    vtype_enc = -1
    for col in ["vessel_type", "vessel_type_key"]:
        if col in pings.columns:
            vt = pings[col].dropna().iloc[0] if len(pings[col].dropna()) > 0 else None
            if vt:
                # Try unified map first, then simulator map
                unified = LOADER_TO_UNIFIED.get(str(vt), SIMULATOR_TO_UNIFIED.get(str(vt), None))
                if unified:
                    vtype_enc = VT_ENC.get(unified, -1)
            break
    f["vessel_type_enc"] = float(vtype_enc)

    # ── Proximity to reference points ──
    if reference_points:
        clat, clon = f["centroid_lat"], f["centroid_lon"]
        if not np.isnan(clat):
            if "ports" in reference_points and reference_points["ports"]:
                dists = [_hav_nm(clat, clon, p["lat"], p["lon"])
                         for p in reference_points["ports"]]
                f["dist_to_port_nm"] = float(min(dists))
            if "fishing_grounds" in reference_points and reference_points["fishing_grounds"]:
                dists = [_hav_nm(clat, clon, p["lat"], p["lon"])
                         for p in reference_points["fishing_grounds"]]
                f["dist_to_fishing_nm"] = float(min(dists))

    # ── Nav status ──
    if "nav_status" in pings.columns:
        ns = pd.to_numeric(pings["nav_status"], errors="coerce").fillna(-1).values
        f["pct_fishing_status"]  = float(np.mean(ns == 7))
        f["pct_anchored_status"] = float(np.mean(np.isin(ns, [1, 5])))

    # ── 2+ pings: dynamics ──
    if n >= 2:
        # Gap stats
        if "obs_span_min" in f and not np.isnan(f.get("obs_span_min", NaN)):
            if "_ts" in pings.columns:
                dt_min = pings["_ts"].diff().dt.total_seconds().fillna(0).values / 60
                f["n_gaps_10min"] = float(np.sum(dt_min > 10))
                f["max_gap_min"]  = float(np.max(dt_min))

        if not np.all(np.isnan(sog)) and n >= 2:
            span = f.get("obs_span_min", 0) or 0
            if span > 0:
                f["acceleration"] = float((np.nanmean(sog[-3:]) - np.nanmean(sog[:3])) / span)

        # Displacement
        lats_v = lats[~np.isnan(lats)]
        lons_v = lons[~np.isnan(lons)]
        if len(lats_v) >= 2:
            f["displacement_nm"] = float(_hav_nm(lats_v[0], lons_v[0],
                                                  lats_v[-1], lons_v[-1]))

        # Heading changes
        if len(valid_cog) >= 2:
            diffs = [_angular_diff(valid_cog[i], valid_cog[i - 1])
                     for i in range(1, len(valid_cog))]
            f["mean_heading_change"] = float(np.mean(diffs))
            f["max_heading_change"]  = float(np.max(diffs))

    # ── 4+ pings: speed patterns ──
    if n >= 4 and not np.all(np.isnan(sog)):
        sog_v = sog[~np.isnan(sog)]
        if len(sog_v) >= 4:
            f["pct_slow"]  = float(np.mean(sog_v < 1.0))
            f["pct_vslow"] = float(np.mean(sog_v < 0.3))
            f["pct_fast"]  = float(np.mean(sog_v > 14.0))
            # SOG trend (positive = accelerating)
            t_idx = np.linspace(0, 1, len(sog_v))
            try:
                slope = float(np.polyfit(t_idx, sog_v, 1)[0])
                f["sog_trend"] = slope
            except Exception:
                pass

    # ── 6+ pings: track geometry ──
    if n >= 6:
        lats_v = lats[~np.isnan(lats)]
        lons_v = lons[~np.isnan(lons)]
        if len(lats_v) >= 6:
            # Path length
            path_nm = sum(_hav_nm(lats_v[i - 1], lons_v[i - 1], lats_v[i], lons_v[i])
                          for i in range(1, len(lats_v)))
            displ = f.get("displacement_nm", NaN)
            if path_nm > 0.01 and not np.isnan(displ):
                f["net_to_gross"] = float(min(1.0, displ / path_nm))

        if len(valid_cog) >= 6:
            f["cog_std"] = float(np.radians(np.std(valid_cog)))  # circular approx
            # Zig-zag: count of direction reversals
            if len(valid_cog) >= 3:
                diffs = np.array([_angular_diff(valid_cog[i], valid_cog[i - 1])
                                  for i in range(1, len(valid_cog))])
                f["zig_zag"] = float(np.sum(diffs > 30) / len(diffs))

    # ── 10+ pings: spatial pattern ──
    if n >= 10:
        lats_v = lats[~np.isnan(lats)]
        lons_v = lons[~np.isnan(lons)]
        if len(lats_v) >= 10:
            lat_r = float(lats_v.max() - lats_v.min())
            lon_r = float(lons_v.max() - lons_v.min())
            f["lat_range"] = lat_r
            f["lon_range"] = lon_r
            f["bbox_area"] = lat_r * lon_r

            path_nm = sum(_hav_nm(lats_v[i - 1], lons_v[i - 1], lats_v[i], lons_v[i])
                          for i in range(1, len(lats_v)))
            if path_nm > 0.01:
                try:
                    from scipy.spatial import ConvexHull
                    coords = np.column_stack([lons_v * 111 * np.cos(np.radians(np.mean(lats_v))),
                                              lats_v * 111])
                    if len(np.unique(coords, axis=0)) >= 4:
                        hull = ConvexHull(coords)
                        hull_nm2 = hull.volume  # area in "km²-ish" for 2D
                        f["loiter_index"] = float(min(1.0, hull_nm2 / (path_nm ** 2 + 1e-6)))
                except Exception:
                    f["loiter_index"] = float(lat_r * lon_r / (path_nm ** 2 + 1e-6))

        if len(valid_cog) >= 10:
            diffs = np.array([_angular_diff(valid_cog[i], valid_cog[i - 1])
                               for i in range(1, len(valid_cog))])
            f["mean_turn_rate"] = float(np.mean(diffs))

    return np.array([f.get(k, NaN) for k in PARTIAL_FEATURES], dtype=np.float32)


# ── Confidence calibration ────────────────────────────────────────────────────

def compute_confidence(n_obs: int, sensor_type: str, feat_vec: np.ndarray) -> float:
    """Calibrated confidence: scales with observations, sensor quality, feature completeness."""
    smeta        = SENSOR_TYPES.get(sensor_type, SENSOR_TYPES["ais"])
    w_sensor     = smeta["quality"]
    w_obs        = min(1.0, np.log1p(n_obs) / np.log1p(20))   # saturates at ~20
    feat_complete = float(np.mean(~np.isnan(feat_vec)))
    return float(0.30 * w_sensor + 0.45 * w_obs + 0.25 * feat_complete)


# ── Parallel training data builder ───────────────────────────────────────────

def _window_activity_label(window: pd.DataFrame) -> str | None:
    """
    Derive the dominant activity label for a window using nav_status where possible,
    falling back to the true_activity column.

    Nav-status takes priority over pre-assigned labels because it is a per-ping
    ground truth signal. This is critical for partial-track training: a fishing
    vessel at 14 kn is transiting (nav_status=0), not fishing, even if its
    vessel_type is "fishing".
    """
    # 1. Try nav_status (per-ping ITU ground truth)
    if "nav_status" in window.columns:
        ns = pd.to_numeric(window["nav_status"], errors="coerce").dropna().astype(int)
        ns_acts = ns.map(NAV_STATUS_ACTIVITY).dropna()
        ns_acts = ns_acts[ns_acts != "unknown"]
        if len(ns_acts) > 0:
            mode = ns_acts.mode().iloc[0]
            if mode in ACTIVITY_LABELS:
                return mode

    # 2. Fall back to pre-assigned true_activity
    if "true_activity" in window.columns:
        acts = window["true_activity"].dropna()
        acts = acts[(acts != "unknown") & acts.isin(ACTIVITY_LABELS)]
        if len(acts) > 0:
            return acts.mode().iloc[0]

    return None


def _build_partial_examples_for_vessel(
    mmsi: str,
    grp: pd.DataFrame,
    sensor_type: str,
    n_lengths: List[int],
    reference_points: Dict | None,
) -> List[Dict]:
    """Build partial-track training examples for one vessel at multiple track lengths."""
    ts_col = "timestamp" if "timestamp" in grp.columns else None
    if ts_col:
        grp = grp.sort_values(ts_col).reset_index(drop=True)

    # Vessel-level type (stable across the track)
    true_vtype = None
    for col in ["vessel_type", "vessel_type_key"]:
        if col in grp.columns:
            vt = grp[col].dropna()
            if len(vt) > 0:
                raw_vt = vt.mode().iloc[0]
                true_vtype = LOADER_TO_UNIFIED.get(
                    raw_vt, SIMULATOR_TO_UNIFIED.get(raw_vt, "unknown"))
            break

    total = len(grp)
    rows = []
    for n_obs in n_lengths:
        if n_obs > total:
            continue
        n_samples = min(5, max(1, total // n_obs))
        for _ in range(n_samples):
            start = np.random.randint(0, max(1, total - n_obs + 1))
            window = grp.iloc[start: start + n_obs]

            # Window-level activity label (ping-level nav_status preferred)
            true_activity = _window_activity_label(window)

            feat = extract_partial_features(window, sensor_type, reference_points)
            rows.append({
                "mmsi":          mmsi,
                "n_obs":         n_obs,
                "sensor_type":   sensor_type,
                "true_activity": true_activity,
                "true_vtype":    true_vtype,
                "features":      feat,
            })

    return rows


def build_training_data(
    df: pd.DataFrame,
    sensor_type: str = "ais",
    n_lengths: List[int] | None = None,
    reference_points: Dict | None = None,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """
    Build partial-track training data from a normalised AIS DataFrame.
    Creates examples at multiple track lengths to teach robustness to short tracks.
    """
    if n_lengths is None:
        n_lengths = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50]

    groups = [(mmsi, grp.copy()) for mmsi, grp in df.groupby("mmsi") if len(grp) >= 3]

    results = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
        delayed(_build_partial_examples_for_vessel)(
            mmsi, grp, sensor_type, n_lengths, reference_points
        )
        for mmsi, grp in groups
    )

    rows = [r for sub in results for r in sub]
    if not rows:
        return pd.DataFrame()

    feat_df = pd.DataFrame({
        "mmsi":          [r["mmsi"] for r in rows],
        "n_obs":         [r["n_obs"] for r in rows],
        "sensor_type":   [r["sensor_type"] for r in rows],
        "true_activity": [r["true_activity"] for r in rows],
        "true_vtype":    [r["true_vtype"] for r in rows],
    })
    feat_arr = np.stack([r["features"] for r in rows])
    for i, col in enumerate(PARTIAL_FEATURES):
        feat_df[col] = feat_arr[:, i]

    return feat_df


# ── Classifier ────────────────────────────────────────────────────────────────

class PartialTrackClassifier:
    """
    Activity and vessel-type classifier for partial tracks.

    Handles N = 1 .. ∞ observations from any sensor type.
    Uses XGBoost (GPU if available) for native NaN handling.

    Example
    -------
    clf = PartialTrackClassifier()
    clf.fit(train_df)                # DataFrame with true_activity / true_vtype cols

    # Single EO observation
    result = clf.predict_single(lat=5.5, lon=104.2, heading=185, sensor_type="eo")

    # Short AIS burst (5 pings before going dark)
    result = clf.predict_track(pings_df, sensor_type="ais")
    """

    def __init__(self):
        self._act_clf  = make_activity_classifier(n_classes=len(ACTIVITY_LABELS))
        self._type_clf = make_type_classifier(n_classes=len(UNIFIED_VESSEL_TYPES))
        self._trained  = False

    def fit(self, train_df: pd.DataFrame) -> "PartialTrackClassifier":
        """Train on output of build_training_data()."""
        feat_cols = PARTIAL_FEATURES
        X = train_df[feat_cols].values.astype(np.float32)

        # Activity model — only rows with known activity
        act_mask = train_df["true_activity"].notna() & \
                   train_df["true_activity"].isin(ACTIVITY_LABELS)
        if act_mask.sum() >= 20:
            self._act_clf.fit(X[act_mask], train_df.loc[act_mask, "true_activity"].values)

        # Vessel type model — only rows with known type
        vt_mask = train_df["true_vtype"].notna() & \
                  train_df["true_vtype"].isin(UNIFIED_VESSEL_TYPES)
        if vt_mask.sum() >= 20:
            self._type_clf.fit(X[vt_mask], train_df.loc[vt_mask, "true_vtype"].values)

        self._trained = True
        return self

    def predict_track(
        self,
        pings: pd.DataFrame | List[Dict],
        sensor_type: str = "ais",
        reference_points: Dict | None = None,
    ) -> Dict[str, Any]:
        """
        Classify a partial track.

        Returns
        -------
        dict with keys:
          activity            — predicted activity label
          activity_proba      — dict of {label: probability}
          vessel_type         — predicted vessel type label
          vessel_type_proba   — dict of {type: probability}
          confidence          — [0,1] overall confidence
          n_obs               — number of observations used
          sensor_type         — sensor used
        """
        if not isinstance(pings, pd.DataFrame):
            pings = pd.DataFrame(pings)

        feat = extract_partial_features(pings, sensor_type, reference_points)
        X    = feat.reshape(1, -1).astype(np.float32)
        n    = int(feat[PARTIAL_FEATURES.index("n_obs")])

        result = {
            "n_obs":       n,
            "sensor_type": sensor_type,
            "confidence":  compute_confidence(n, sensor_type, feat),
        }

        if self._trained:
            # Activity
            act_proba = self._act_clf.predict_proba(X)[0]
            act_class = self._act_clf.classes_
            result["activity"]       = str(act_class[np.argmax(act_proba)])
            result["activity_proba"] = {str(c): float(p) for c, p in zip(act_class, act_proba)}

            # Vessel type
            vt_proba  = self._type_clf.predict_proba(X)[0]
            vt_class  = self._type_clf.classes_
            result["vessel_type"]       = str(vt_class[np.argmax(vt_proba)])
            result["vessel_type_proba"] = {str(c): float(p) for c, p in zip(vt_class, vt_proba)}
        else:
            result["activity"]       = "unknown"
            result["vessel_type"]    = "unknown"
            result["activity_proba"] = {}
            result["vessel_type_proba"] = {}

        return result

    def predict_single(
        self,
        lat: float,
        lon: float,
        sog: float | None = None,
        heading: float | None = None,
        timestamp: str | None = None,
        vessel_type: str | None = None,
        length_m: float | None = None,
        nav_status: int | None = None,
        sensor_type: str = "eo",
        reference_points: Dict | None = None,
    ) -> Dict[str, Any]:
        """Classify from a single observation (point-in-time)."""
        ping = {"lat": lat, "lon": lon}
        if sog         is not None: ping["sog"]         = sog
        if heading     is not None: ping["heading"]      = heading
        if timestamp   is not None: ping["timestamp"]    = timestamp
        if vessel_type is not None: ping["vessel_type"]  = vessel_type
        if length_m    is not None: ping["length_m"]     = length_m
        if nav_status  is not None: ping["nav_status"]   = nav_status
        return self.predict_track([ping], sensor_type=sensor_type,
                                   reference_points=reference_points)

    def batch_predict(
        self,
        df: pd.DataFrame,
        sensor_type: str = "ais",
        reference_points: Dict | None = None,
        n_jobs: int = -1,
    ) -> pd.DataFrame:
        """
        Predict activity and vessel type for all vessels in a normalised AIS DataFrame.
        Parallelised across vessels using all CPU cores.

        Returns vessel-level DataFrame with predictions + confidence.
        """
        groups = [(mmsi, grp.copy()) for mmsi, grp in df.groupby("mmsi")]

        def _pred_one(mmsi, grp):
            r = self.predict_track(grp, sensor_type, reference_points)
            r["mmsi"] = mmsi
            r["n_pings_total"] = len(grp)
            return r

        results = Parallel(n_jobs=n_jobs, backend="loky", verbose=0)(
            delayed(_pred_one)(mmsi, grp) for mmsi, grp in groups
        )

        rows = []
        for r in results:
            row = {
                "mmsi":          r["mmsi"],
                "n_pings_total": r.get("n_pings_total", 0),
                "n_obs_used":    r.get("n_obs", 0),
                "sensor_type":   r.get("sensor_type", sensor_type),
                "pred_activity": r.get("activity", "unknown"),
                "pred_vtype":    r.get("vessel_type", "unknown"),
                "confidence":    r.get("confidence", 0.0),
            }
            for act in ACTIVITY_LABELS:
                row[f"prob_{act}"] = r.get("activity_proba", {}).get(act, 0.0)
            rows.append(row)

        return pd.DataFrame(rows)

    def evaluate(
        self,
        test_df: pd.DataFrame,
        by_n_obs: bool = True,
    ) -> Dict[str, Any]:
        """
        Evaluate on test data from build_training_data().
        If by_n_obs=True, also compute per-track-length accuracy breakdown.
        """
        from sklearn.metrics import classification_report, f1_score

        feat = test_df[PARTIAL_FEATURES].values.astype(np.float32)
        results = {}

        # Activity
        act_mask = test_df["true_activity"].notna() & test_df["true_activity"].isin(ACTIVITY_LABELS)
        if act_mask.sum() >= 10:
            X_a   = feat[act_mask]
            y_a   = test_df.loc[act_mask, "true_activity"].values
            preds = self._act_clf.predict(X_a)
            results["activity_f1_macro"]    = float(f1_score(y_a, preds, average="macro",
                                                              zero_division=0))
            results["activity_f1_weighted"] = float(f1_score(y_a, preds, average="weighted",
                                                              zero_division=0))
            results["activity_report"] = classification_report(
                y_a, preds, zero_division=0, output_dict=True)

        # Vessel type
        vt_mask = test_df["true_vtype"].notna() & test_df["true_vtype"].isin(UNIFIED_VESSEL_TYPES)
        if vt_mask.sum() >= 10:
            X_v   = feat[vt_mask]
            y_v   = test_df.loc[vt_mask, "true_vtype"].values
            preds = self._type_clf.predict(X_v)
            results["vtype_f1_macro"]    = float(f1_score(y_v, preds, average="macro",
                                                           zero_division=0))
            results["vtype_f1_weighted"] = float(f1_score(y_v, preds, average="weighted",
                                                            zero_division=0))
            results["vtype_report"] = classification_report(
                y_v, preds, zero_division=0, output_dict=True)

        # Per-N breakdown
        if by_n_obs and "n_obs" in test_df.columns and "activity_report" in results:
            by_n = {}
            for n_val in sorted(test_df["n_obs"].unique()):
                sub = test_df[(test_df["n_obs"] == n_val) & act_mask]
                if len(sub) < 5:
                    continue
                X_n   = feat[sub.index]
                y_n   = sub["true_activity"].values
                preds = self._act_clf.predict(X_n)
                by_n[int(n_val)] = float(f1_score(y_n, preds, average="weighted",
                                                    zero_division=0))
            results["activity_f1_by_n_obs"] = by_n

        return results

    def save(self, path: str | Path):
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"act_clf": self._act_clf, "type_clf": self._type_clf,
                         "trained": self._trained}, f)

    def load(self, path: str | Path) -> "PartialTrackClassifier":
        import pickle
        with open(path, "rb") as f:
            d = pickle.load(f)
        self._act_clf  = d["act_clf"]
        self._type_clf = d["type_clf"]
        self._trained  = d["trained"]
        return self
