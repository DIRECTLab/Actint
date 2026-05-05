"""
Dark Period / Custody Gap Predictor

When a vessel's AIS goes dark (or any sensor loses custody), this module:
  1. Dead-reckons a probability cone using last known state (SOG, COG, heading).
  2. Propagates uncertainty using a kinematic noise model calibrated on AIS data.
  3. Predicts likely reacquisition zone (lat/lon bbox + probability contour).
  4. Scores reacquisition probability at candidate sensor-coverage regions.
  5. Learns vessel-class departure/return patterns from historical dark periods.

Usage:
    from src.dark_period_predictor import DarkPeriodPredictor
    dpp = DarkPeriodPredictor()
    dpp.fit(df)                          # learn per-class dark patterns
    cone = dpp.predict_cone(last_state, dt_hours=6.0)
    zones = dpp.reacquisition_zones(cone, sensor_coverages)
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Dict

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_NM_PER_DEG_LAT = 60.0

# Per-class speed uncertainty (knots/hr) — higher for erratic vessel types
_CLASS_SPEED_SIGMA = {
    "fishing":        1.5,
    "trawler":        1.8,
    "longliner":      1.2,
    "purse_seiner":   2.0,
    "tanker":         0.5,
    "cargo":          0.6,
    "passenger":      0.4,
    "tug":            2.0,
    "sailing":        2.5,
    "naval":          3.0,   # high manoeuvre capability
    "pleasure_craft": 3.0,
    "support_vessel": 2.0,
    "hsc":            4.0,
    "other":          2.0,
    "unknown":        2.5,
}

# Per-class heading drift (degrees/hr std)
_CLASS_HDG_SIGMA = {
    "fishing":        25.0,
    "trawler":        30.0,
    "tanker":         5.0,
    "cargo":          5.0,
    "passenger":      4.0,
    "tug":            45.0,
    "sailing":        40.0,
    "naval":          60.0,
    "pleasure_craft": 50.0,
    "hsc":            30.0,
    "unknown":        30.0,
}


# ══════════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VesselState:
    mmsi:        int
    timestamp:   pd.Timestamp
    lat:         float
    lon:         float
    sog_kn:      float         # speed over ground, knots
    cog_deg:     float         # course over ground, degrees true
    vessel_type: str = "unknown"
    heading:     Optional[float] = None
    nav_status:  Optional[int]   = None


@dataclass
class UncertaintyCone:
    mmsi:          int
    t0:            pd.Timestamp
    dt_hours:      float
    origin_lat:    float
    origin_lon:    float
    # Monte Carlo samples at t0 + dt_hours
    sample_lats:   np.ndarray = field(default_factory=lambda: np.array([]))
    sample_lons:   np.ndarray = field(default_factory=lambda: np.array([]))
    # Summary statistics
    mean_lat:      float = 0.0
    mean_lon:      float = 0.0
    std_lat_nm:    float = 0.0
    std_lon_nm:    float = 0.0
    radius_95_nm:  float = 0.0
    bbox:          tuple = ()  # (lat_min, lat_max, lon_min, lon_max)


# ══════════════════════════════════════════════════════════════════════════════
# Dark Period Predictor
# ══════════════════════════════════════════════════════════════════════════════

class DarkPeriodPredictor:
    """
    Dead-reckoning with uncertainty propagation for vessel custody gaps.
    """

    def __init__(self, n_samples: int = 2000, seed: int = 42):
        self._n_samples = n_samples
        self._rng       = np.random.default_rng(seed)
        # Learned per-class dark-period distributions (from fit())
        self._dark_dists: Dict[str, dict] = {}

    # ──────────────────────────────────────────────────────────────────────────
    def fit(self, df: pd.DataFrame) -> "DarkPeriodPredictor":
        """
        Learn typical dark-period characteristics per vessel class.

        Args:
            df: AIS DataFrame with mmsi, timestamp, vessel_type, sog columns.
                Rows with >30-min gaps between consecutive pings for the same
                MMSI are treated as dark periods.
        """
        df = df.copy()
        if not np.issubdtype(df["timestamp"].dtype, np.datetime64):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp", "mmsi"]).sort_values(["mmsi", "timestamp"])

        dark_records = []
        for mmsi, grp in df.groupby("mmsi"):
            grp = grp.sort_values("timestamp")
            ts_pd = pd.to_datetime(grp["timestamp"].values)
            gaps_s = np.array([(ts_pd[i+1] - ts_pd[i]).total_seconds()
                               for i in range(len(ts_pd)-1)])

            vtype = "unknown"
            if "vessel_type" in grp.columns:
                m = grp["vessel_type"].mode()
                if len(m) > 0:
                    vtype = str(m.iloc[0])

            for gap in gaps_s[gaps_s > 1800]:  # >30 min
                dark_records.append({"vessel_type": vtype,
                                     "gap_hours": gap / 3600.0})

        if not dark_records:
            log.warning("[dark] No dark periods found in training data")
            return self

        dr = pd.DataFrame(dark_records)
        for vtype, grp in dr.groupby("vessel_type"):
            gaps = grp["gap_hours"].values
            self._dark_dists[vtype] = {
                "median_h": float(np.median(gaps)),
                "p90_h":    float(np.percentile(gaps, 90)),
                "p99_h":    float(np.percentile(gaps, 99)),
                "n":        len(gaps),
            }

        log.info("[dark] Learned dark patterns for %d vessel types",
                 len(self._dark_dists))
        return self

    # ──────────────────────────────────────────────────────────────────────────
    def predict_cone(self, state: VesselState,
                     dt_hours: float,
                     n_waypoints: int = 6) -> UncertaintyCone:
        """
        Monte Carlo dead-reckoning cone.

        Args:
            state:      Last known vessel state.
            dt_hours:   Duration of dark period to project.
            n_waypoints: Number of intermediate time steps.

        Returns:
            UncertaintyCone with Monte Carlo samples at t0 + dt_hours.
        """
        vtype      = state.vessel_type
        spd_sigma  = _CLASS_SPEED_SIGMA.get(vtype, 2.0)
        hdg_sigma  = _CLASS_HDG_SIGMA.get(vtype, 30.0)

        N  = self._n_samples
        dt = dt_hours / n_waypoints   # step size in hours

        # Initialise particles
        lats  = np.full(N, state.lat)
        lons  = np.full(N, state.lon)
        spds  = np.full(N, max(state.sog_kn, 0.0))
        hdgs  = np.full(N, state.cog_deg % 360)

        for _ in range(n_waypoints):
            # Random walk on speed and heading
            spds = np.clip(
                spds + self._rng.normal(0, spd_sigma * np.sqrt(dt), N),
                0, 35,
            )
            hdgs = (
                hdgs + self._rng.normal(0, hdg_sigma * np.sqrt(dt), N)
            ) % 360

            # Propagate position
            rad    = np.radians(hdgs)
            dist   = spds * dt   # nautical miles
            cos_lat = np.cos(np.radians(lats))

            lats = lats + (dist * np.cos(rad)) / _NM_PER_DEG_LAT
            lons = lons + (dist * np.sin(rad)) / (_NM_PER_DEG_LAT * cos_lat)

        # Clip to valid geographic range
        lats = np.clip(lats, -90, 90)
        lons = ((lons + 180) % 360) - 180

        # Derive summary stats
        mean_lat = float(lats.mean())
        mean_lon = float(lons.mean())
        std_lat  = float(lats.std() * _NM_PER_DEG_LAT)
        cos_c    = np.cos(np.radians(mean_lat))
        std_lon  = float(lons.std() * _NM_PER_DEG_LAT * cos_c)

        dists_nm = np.sqrt(
            ((lats - mean_lat) * _NM_PER_DEG_LAT)**2 +
            ((lons - mean_lon) * _NM_PER_DEG_LAT * cos_c)**2
        )
        r95 = float(np.percentile(dists_nm, 95))

        p2  = np.percentile(lats, 2.5)
        p97 = np.percentile(lats, 97.5)
        q2  = np.percentile(lons, 2.5)
        q97 = np.percentile(lons, 97.5)

        return UncertaintyCone(
            mmsi=state.mmsi,
            t0=state.timestamp,
            dt_hours=dt_hours,
            origin_lat=state.lat,
            origin_lon=state.lon,
            sample_lats=lats,
            sample_lons=lons,
            mean_lat=mean_lat,
            mean_lon=mean_lon,
            std_lat_nm=std_lat,
            std_lon_nm=std_lon,
            radius_95_nm=r95,
            bbox=(float(p2), float(p97), float(q2), float(q97)),
        )

    # ──────────────────────────────────────────────────────────────────────────
    def reacquisition_probability(self,
                                  cone: UncertaintyCone,
                                  sensor_lats: np.ndarray,
                                  sensor_lons: np.ndarray,
                                  sensor_radii_nm: np.ndarray) -> np.ndarray:
        """
        Estimate probability that the vessel is within each sensor's coverage.

        Args:
            cone:             UncertaintyCone from predict_cone().
            sensor_lats/lons: Centre coordinates of sensor footprints.
            sensor_radii_nm:  Coverage radius (nm) for each sensor.

        Returns:
            Array of probabilities [0,1], one per sensor.
        """
        N   = len(cone.sample_lats)
        probs = np.zeros(len(sensor_lats), dtype=np.float32)

        for i, (slat, slon, srad) in enumerate(
                zip(sensor_lats, sensor_lons, sensor_radii_nm)):
            cos_lat = np.cos(np.radians(slat))
            dlat = (cone.sample_lats - slat) * _NM_PER_DEG_LAT
            dlon = (cone.sample_lons - slon) * _NM_PER_DEG_LAT * cos_lat
            dist = np.sqrt(dlat**2 + dlon**2)
            probs[i] = float((dist <= srad).sum()) / N

        return probs

    # ──────────────────────────────────────────────────────────────────────────
    def expected_return_hours(self, vessel_type: str) -> dict:
        """
        Return expected dark-period duration statistics for a vessel class.
        Falls back to global averages if class not seen in training data.
        """
        d = self._dark_dists.get(
            vessel_type,
            self._dark_dists.get("unknown", {"median_h": 4.0, "p90_h": 12.0,
                                              "p99_h": 48.0, "n": 0})
        )
        return d

    # ──────────────────────────────────────────────────────────────────────────
    def summarise(self, state: VesselState, dt_hours: float) -> dict:
        """
        Convenience method: run predict_cone and return a human-readable summary.
        """
        cone = self.predict_cone(state, dt_hours)
        dark_stats = self.expected_return_hours(state.vessel_type)
        return {
            "mmsi":              state.mmsi,
            "vessel_type":       state.vessel_type,
            "dark_hours":        dt_hours,
            "mean_position":     (round(cone.mean_lat, 4), round(cone.mean_lon, 4)),
            "uncertainty_95_nm": round(cone.radius_95_nm, 1),
            "bbox":              tuple(round(v, 4) for v in cone.bbox),
            "dark_median_h":     dark_stats.get("median_h", "unknown"),
            "dark_p90_h":        dark_stats.get("p90_h", "unknown"),
        }

    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def extract_dark_periods(df: pd.DataFrame,
                             gap_threshold_min: float = 30.0) -> pd.DataFrame:
        """
        Extract all dark periods (AIS gaps) from a normalised AIS DataFrame.

        Returns DataFrame with: mmsi, dark_start, dark_end, gap_hours,
        last_lat, last_lon, last_sog, last_cog, vessel_type.
        """
        df = df.copy()
        if not np.issubdtype(df["timestamp"].dtype, np.datetime64):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values(["mmsi", "timestamp"])

        records = []
        for mmsi, grp in df.groupby("mmsi"):
            grp  = grp.sort_values("timestamp").reset_index(drop=True)
            ts   = grp["timestamp"].values

            vtype = "unknown"
            if "vessel_type" in grp.columns:
                m = grp["vessel_type"].mode()
                if len(m) > 0:
                    vtype = str(m.iloc[0])

            for j in range(len(grp) - 1):
                t0 = pd.Timestamp(ts[j])
                t1 = pd.Timestamp(ts[j+1])
                gap_s = (t1 - t0).total_seconds()
                if gap_s >= gap_threshold_min * 60:
                    row = grp.iloc[j]
                    records.append({
                        "mmsi":        mmsi,
                        "dark_start":  t0,
                        "dark_end":    t1,
                        "gap_hours":   round(gap_s / 3600.0, 3),
                        "last_lat":    float(row.get("lat", np.nan)),
                        "last_lon":    float(row.get("lon", np.nan)),
                        "last_sog":    float(row.get("sog", np.nan)),
                        "last_cog":    float(row.get("cog", np.nan)),
                        "vessel_type": vtype,
                    })

        return pd.DataFrame(records)
