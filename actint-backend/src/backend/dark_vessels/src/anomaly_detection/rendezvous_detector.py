"""
Rendezvous / Proximity Event Detector

Identifies multi-vessel meeting events that may indicate:
  - Ship-to-ship (STS) fuel / cargo transfer
  - Fishing fleet coordination / tender vessel rendezvous
  - Vessel spoofing / identity swap
  - Clandestine meetings (dark periods + sudden proximity)

Algorithm:
  1. Build spatial index (rtree) over all pings at each 5-min epoch.
  2. Detect pairwise proximity events (<0.5 nm, ≥10 min).
  3. Score each event by vessel-type pair, darkness, location, convergence rate.
  4. Return event table + per-vessel risk elevation.

Usage:
    from src.rendezvous_detector import RendezvousDetector
    rz = RendezvousDetector()
    events = rz.detect(df)          # df = normalised AIS DataFrame
    vessel_risk = rz.vessel_risk_scores(events)
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_NM_PER_DEG_LAT = 60.0          # 1° lat ≈ 60 nm
_PROX_NM        = 0.5           # proximity threshold (nm)
_MIN_DURATION_S = 600           # 10 minutes minimum event duration
_EPOCH_BIN_S    = 300           # 5-minute epoch for binning

# Risk multipliers by vessel-type pair (symmetric)
_PAIR_RISK = {
    frozenset({"tanker",  "tanker"}):          0.90,
    frozenset({"tanker",  "cargo"}):           0.60,
    frozenset({"tanker",  "fishing"}):         0.50,
    frozenset({"fishing", "fishing"}):         0.40,
    frozenset({"fishing", "support_vessel"}):  0.55,
    frozenset({"cargo",   "cargo"}):           0.30,
    frozenset({"naval",   "tanker"}):          0.20,   # legitimate escort
}
_DEFAULT_PAIR_RISK = 0.25


# ══════════════════════════════════════════════════════════════════════════════
class RendezvousDetector:
    """
    Detects and scores vessel rendezvous events from AIS track data.
    """

    def __init__(self,
                 prox_nm: float     = _PROX_NM,
                 min_duration_s: int = _MIN_DURATION_S,
                 epoch_bin_s: int    = _EPOCH_BIN_S):
        self.prox_nm        = prox_nm
        self.min_duration_s = min_duration_s
        self.epoch_bin_s    = epoch_bin_s

    # ──────────────────────────────────────────────────────────────────────────
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entry point.

        Args:
            df: normalised AIS DataFrame with columns:
                mmsi, timestamp (datetime64), lat, lon,
                vessel_type (optional), sog (optional), pct_dark (optional)

        Returns:
            events DataFrame with columns:
                mmsi_a, mmsi_b, type_a, type_b,
                start_time, end_time, duration_min,
                mean_dist_nm, min_dist_nm,
                centroid_lat, centroid_lon,
                both_dark, risk_score
        """
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        if not np.issubdtype(df["timestamp"].dtype, np.datetime64):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp", "lat", "lon"])
        df["epoch"] = (
            df["timestamp"].astype(np.int64) // (self.epoch_bin_s * 10**9)
        ).astype(int)

        vessel_type = {}
        if "vessel_type" in df.columns:
            for mmsi, vt in df.groupby("mmsi")["vessel_type"].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "unknown").items():
                vessel_type[mmsi] = str(vt)

        # ── Per-epoch proximity scan ──────────────────────────────────────────
        candidate_pairs: dict[tuple, list] = {}   # (mmsi_a, mmsi_b) -> [epoch ts, dist]

        for epoch, epoch_df in df.groupby("epoch"):
            if len(epoch_df) < 2:
                continue
            epoch_ts = epoch_df["timestamp"].min()
            lats = epoch_df["lat"].values
            lons = epoch_df["lon"].values
            mmsis = epoch_df["mmsi"].values
            cos_lat = np.cos(np.radians(lats.mean()))

            # Vectorised pairwise distance (flat-earth approximation)
            dlat = (lats[:, None] - lats[None, :]) * _NM_PER_DEG_LAT
            dlon = (lons[:, None] - lons[None, :]) * _NM_PER_DEG_LAT * cos_lat
            dist = np.sqrt(dlat**2 + dlon**2)

            rows, cols = np.where(
                (dist < self.prox_nm) & (np.arange(len(mmsis))[:, None] < np.arange(len(mmsis))[None, :])
            )
            for r, c in zip(rows, cols):
                key = (int(mmsis[r]), int(mmsis[c]))
                candidate_pairs.setdefault(key, []).append((epoch_ts, float(dist[r, c])))

        # ── Merge consecutive epochs into events ──────────────────────────────
        events = []
        for (mmsi_a, mmsi_b), hits in candidate_pairs.items():
            hits.sort(key=lambda x: x[0])
            # Split into contiguous runs separated by >2 epochs
            runs = []
            current = [hits[0]]
            for ts, d in hits[1:]:
                gap = (ts - current[-1][0]).total_seconds()
                if gap <= self.epoch_bin_s * 3:
                    current.append((ts, d))
                else:
                    runs.append(current)
                    current = [(ts, d)]
            runs.append(current)

            for run in runs:
                duration_s = (run[-1][0] - run[0][0]).total_seconds() + self.epoch_bin_s
                if duration_s < self.min_duration_s:
                    continue
                dists = [d for _, d in run]
                events.append({
                    "mmsi_a":       mmsi_a,
                    "mmsi_b":       mmsi_b,
                    "type_a":       vessel_type.get(mmsi_a, "unknown"),
                    "type_b":       vessel_type.get(mmsi_b, "unknown"),
                    "start_time":   run[0][0],
                    "end_time":     run[-1][0],
                    "duration_min": round(duration_s / 60, 1),
                    "mean_dist_nm": round(float(np.mean(dists)), 3),
                    "min_dist_nm":  round(float(np.min(dists)), 3),
                    "centroid_lat": float(
                        df[df["mmsi"].isin([mmsi_a, mmsi_b]) &
                           (df["timestamp"] >= run[0][0]) &
                           (df["timestamp"] <= run[-1][0])]["lat"].mean()
                    ),
                    "centroid_lon": float(
                        df[df["mmsi"].isin([mmsi_a, mmsi_b]) &
                           (df["timestamp"] >= run[0][0]) &
                           (df["timestamp"] <= run[-1][0])]["lon"].mean()
                    ),
                })

        if not events:
            return pd.DataFrame()

        ev_df = pd.DataFrame(events)

        # ── Dark flag ─────────────────────────────────────────────────────────
        ev_df["both_dark"] = False
        if "pct_dark" in df.columns:
            dark_mmsis = set(df.groupby("mmsi")["pct_dark"].mean()
                              .pipe(lambda s: s[s > 0.2]).index)
            ev_df["both_dark"] = (
                ev_df["mmsi_a"].isin(dark_mmsis) &
                ev_df["mmsi_b"].isin(dark_mmsis)
            )

        # ── Risk scoring ──────────────────────────────────────────────────────
        ev_df["risk_score"] = ev_df.apply(self._score_event, axis=1)

        log.info("[rendezvous] %d events detected", len(ev_df))
        return ev_df.sort_values("risk_score", ascending=False).reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────────────
    def _score_event(self, row: pd.Series) -> float:
        """Compute risk score [0,1] for a single event."""
        pair_key = frozenset({row["type_a"], row["type_b"]})
        base = _PAIR_RISK.get(pair_key, _DEFAULT_PAIR_RISK)

        # Duration bonus: up to +0.15 for events >2h
        dur_bonus = min(row["duration_min"] / 120.0, 1.0) * 0.15

        # Darkness bonus
        dark_bonus = 0.20 if row.get("both_dark", False) else 0.0

        # Proximity bonus: closer = more suspicious
        prox_bonus = max(0.0, (self.prox_nm - row["min_dist_nm"]) / self.prox_nm) * 0.10

        return min(base + dur_bonus + dark_bonus + prox_bonus, 1.0)

    # ──────────────────────────────────────────────────────────────────────────
    def vessel_risk_scores(self, events: pd.DataFrame) -> pd.Series:
        """
        Returns a Series (index=mmsi, value=max_risk_score) for any vessel
        that appears in at least one rendezvous event.
        """
        if events.empty:
            return pd.Series(dtype=float)

        a = events[["mmsi_a", "risk_score"]].rename(columns={"mmsi_a": "mmsi"})
        b = events[["mmsi_b", "risk_score"]].rename(columns={"mmsi_b": "mmsi"})
        combined = pd.concat([a, b], ignore_index=True)
        return combined.groupby("mmsi")["risk_score"].max()

    # ──────────────────────────────────────────────────────────────────────────
    def convergence_pattern(self, df: pd.DataFrame,
                            mmsi_a: int, mmsi_b: int,
                            event_start: pd.Timestamp,
                            event_end: pd.Timestamp) -> dict:
        """
        Analyse convergence / divergence dynamics for a specific event.
        Returns dict with approach_speed_kn, departure_speed_kn, pattern.
        """
        window = 30 * 60  # 30-minute lookback/lookahead
        a = df[df["mmsi"] == mmsi_a].sort_values("timestamp")
        b = df[df["mmsi"] == mmsi_b].sort_values("timestamp")

        pre_start = event_start - pd.Timedelta(seconds=window)
        post_end  = event_end   + pd.Timedelta(seconds=window)

        approach = self._dist_trend(a, b, pre_start, event_start)
        depart   = self._dist_trend(a, b, event_end,  post_end)

        pattern = "unknown"
        if approach < -0.05 and depart > 0.05:
            pattern = "rendezvous"          # deliberate meet-and-depart
        elif approach < -0.05:
            pattern = "approach_only"
        elif depart > 0.05:
            pattern = "departure_only"
        else:
            pattern = "sustained_proximity"

        return {
            "approach_nm_per_min": approach,
            "departure_nm_per_min": depart,
            "pattern": pattern,
        }

    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _dist_trend(a: pd.DataFrame, b: pd.DataFrame,
                    t0: pd.Timestamp, t1: pd.Timestamp) -> float:
        """Mean rate-of-change of inter-vessel distance (nm/min) over [t0,t1]."""
        aa = a[(a["timestamp"] >= t0) & (a["timestamp"] <= t1)]
        bb = b[(b["timestamp"] >= t0) & (b["timestamp"] <= t1)]
        if len(aa) < 2 or len(bb) < 2:
            return 0.0

        def _dist(r1, r2):
            dlat = (r1["lat"] - r2["lat"]) * 60.0
            dlon = (r1["lon"] - r2["lon"]) * 60.0 * np.cos(np.radians(r1["lat"]))
            return np.sqrt(dlat**2 + dlon**2)

        merged = pd.merge_asof(
            aa.sort_values("timestamp"),
            bb[["timestamp", "lat", "lon"]].sort_values("timestamp"),
            on="timestamp", direction="nearest", suffixes=("_a", "_b"),
        )
        if len(merged) < 2:
            return 0.0
        dists = merged.apply(
            lambda r: _dist(
                {"lat": r["lat_a"], "lon": r["lon_a"]},
                {"lat": r["lat_b"], "lon": r["lon_b"]},
            ), axis=1,
        ).values
        span_min = (merged["timestamp"].iloc[-1] - merged["timestamp"].iloc[0]).total_seconds() / 60
        if span_min < 1:
            return 0.0
        return float((dists[-1] - dists[0]) / span_min)
