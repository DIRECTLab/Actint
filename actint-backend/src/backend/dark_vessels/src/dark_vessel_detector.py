"""
Dark Vessel & AIS Manipulation Detector

Techniques:
  1. Gap analysis    – large temporal gaps suggest intentional AIS-off
  2. Position jumps  – impossible speed between pings = spoofed/replayed position
  3. Identity cloning – same MMSI appearing in multiple distant locations
  4. Speed/COG inconsistency – reported AIS values don't match Doppler/actual track
  5. Flag anomaly    – vessel uses flag known for poor AIS compliance
  6. Loitering in remote area – no plausible reason to be there
"""

import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict


MAX_REALISTIC_SPEED_KN = 40.0  # faster than any commercial vessel

POOR_COMPLIANCE_FLAGS = {
    "VU", "PA", "KM", "TG", "SL", "GN", "GQ", "KH", "MN", "NR",
    "SB", "TV", "WS", "TO", "KI", "PW", "MH",
}

FISHING_FLAGS_OF_CONCERN = {
    "CN", "TW", "VN", "ID",  # distant-water fleets with IUU history
}


def haversine_nm(lat1, lon1, lat2, lon2):
    R = 3440.065
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(max(0.0, a)))


class DarkVesselDetector:

    def __init__(
        self,
        gap_threshold_min: float = 60.0,         # gap > 1h = suspicious
        dark_gap_threshold_min: float = 480.0,   # gap > 8h = likely intentional
        impossible_speed_kn: float = 40.0,
    ):
        self.gap_threshold_min   = gap_threshold_min
        self.dark_gap_threshold_min = dark_gap_threshold_min
        self.impossible_speed_kn = impossible_speed_kn

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze_fleet(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyse every vessel in df.  Returns a per-vessel summary with
        anomaly flags and a composite dark_risk score.
        """
        results = []
        df.rename(columns={"basedatetime": "timestamp"}, inplace=True)
        for mmsi, grp in df.groupby("mmsi"):
            grp = grp.sort_values("timestamp").reset_index(drop=True)
            results.append(self._analyze_vessel(grp))
            print(f"Appended {mmsi} analysis")
        return pd.DataFrame(results)

    def detect_spoofed_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flag individual pings that appear to be position spoofs
        (requires impossible travel from previous ping).
        Returns df with added column `spoof_flag`.
        """
        df = df.sort_values(["mmsi", "timestamp"]).copy()
        df["spoof_flag"] = False
        df["implied_speed_kn"] = np.nan

        for mmsi, grp in df.groupby("mmsi"):
            idx = grp.index.tolist()
            for i in range(1, len(idx)):
                prev = grp.loc[idx[i-1]]
                curr = grp.loc[idx[i]]
                dt_h = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 3600
                if dt_h < 1e-6:
                    continue
                dist_nm = haversine_nm(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
                spd = dist_nm / dt_h
                df.at[idx[i], "implied_speed_kn"] = spd
                if spd > self.impossible_speed_kn:
                    df.at[idx[i], "spoof_flag"] = True

        return df

    def detect_mmsi_clones(self, df: pd.DataFrame,
                            min_separation_nm: float = 500.0) -> List[int]:
        """
        Detect MMSI values appearing at widely separated locations
        within a short time window (possible identity theft / cloning).
        """
        suspicious = []
        for mmsi, grp in df.groupby("mmsi"):
            print(f"Is {mmsi} suspicious?")
            grp = grp.sort_values("timestamp")
            for i in range(len(grp) - 1):
                dt_h = (grp.iloc[i+1]["timestamp"] - grp.iloc[i]["timestamp"]).total_seconds() / 3600
                if dt_h < 0.5:  # less than 30 min apart
                    dist = haversine_nm(
                        grp.iloc[i]["lat"], grp.iloc[i]["lon"],
                        grp.iloc[i+1]["lat"], grp.iloc[i+1]["lon"]
                    )
                    if dist > min_separation_nm:
                        suspicious.append(int(mmsi))
                        break
        return suspicious

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _analyze_vessel(self, grp: pd.DataFrame) -> dict:
        mmsi = int(grp["mmsi"].iloc[0])
        flag = grp["flag"].iloc[0] if "flag" in grp.columns else "XX"
        name = grp["name"].iloc[0]  if "name" in grp.columns else str(mmsi)

        timestamps = grp["timestamp"].values
        lats = grp["lat"].values
        lons = grp["lon"].values
        sog  = grp["sog"].values

        gaps_min = []
        impossible_jumps = 0
        max_implied_speed = 0.0

        for i in range(1, len(grp)):
            dt_h = (grp.iloc[i]["timestamp"] - grp.iloc[i-1]["timestamp"]).total_seconds() / 3600
            dt_m = dt_h * 60
            gaps_min.append(dt_m)

            if dt_h > 1e-6:
                dist_nm = haversine_nm(lats[i-1], lons[i-1], lats[i], lons[i])
                implied = dist_nm / dt_h
                max_implied_speed = max(max_implied_speed, implied)
                if implied > self.impossible_speed_kn:
                    impossible_jumps += 1

        gaps_arr = np.array(gaps_min) if gaps_min else np.array([0.0])
        n_gaps_1h  = int(np.sum(gaps_arr > self.gap_threshold_min))
        n_gaps_8h  = int(np.sum(gaps_arr > self.dark_gap_threshold_min))
        max_gap_h  = float(gaps_arr.max() / 60)
        total_dark_fraction = float(
            (grp["ais_on"].eq(False).sum() / len(grp))
            if "ais_on" in grp.columns else 0.0
        )

        # Flag-based risk
        poor_flag    = flag in POOR_COMPLIANCE_FLAGS
        concern_flag = flag in FISHING_FLAGS_OF_CONCERN
        vessel_type  = grp["vessel_type_key"].iloc[0] if "vessel_type_key" in grp.columns else "unknown"
        is_fishing   = vessel_type in ("trawler", "longliner", "purse_seiner")

        # Composite score
        gap_score  = min(1.0, (n_gaps_1h / 5) * 0.4 + (max_gap_h / 12) * 0.35 + total_dark_fraction * 0.25)
        spoof_score = min(1.0, impossible_jumps / 3)
        flag_score  = 0.3 if poor_flag else (0.2 if (concern_flag and is_fishing) else 0.0)
        dark_risk   = min(1.0, gap_score * 0.6 + spoof_score * 0.3 + flag_score * 0.1)

        # Human-readable flags
        anomaly_flags = []
        if n_gaps_1h > 0:
            anomaly_flags.append(f"AIS_GAPS_{n_gaps_1h}x>1h")
        if n_gaps_8h > 0:
            anomaly_flags.append(f"DARK_PERIODS_{n_gaps_8h}x>8h")
        if impossible_jumps > 0:
            anomaly_flags.append(f"IMPOSSIBLE_JUMPS_{impossible_jumps}")
        if poor_flag:
            anomaly_flags.append("POOR_COMPLIANCE_FLAG")
        if concern_flag and is_fishing:
            anomaly_flags.append("IUU_CONCERN_FLAG+FISHING")
        if total_dark_fraction > 0.2:
            anomaly_flags.append(f"HIGH_DARK_FRACTION_{total_dark_fraction:.0%}")

        return {
            "mmsi": mmsi,
            "name": name,
            "flag": flag,
            "vessel_type": vessel_type,
            "n_pings": len(grp),
            "n_ais_gaps_1h": n_gaps_1h,
            "n_dark_periods_8h": n_gaps_8h,
            "max_gap_h": round(max_gap_h, 2),
            "impossible_jumps": impossible_jumps,
            "max_implied_speed_kn": round(max_implied_speed, 1),
            "dark_fraction": round(total_dark_fraction, 3),
            "poor_compliance_flag": poor_flag,
            "dark_risk_score": round(dark_risk, 3),
            "anomaly_flags": "; ".join(anomaly_flags) if anomaly_flags else "NONE",
        }
