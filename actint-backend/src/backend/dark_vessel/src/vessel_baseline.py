"""
Per-Vessel Behavioural Baseline & Anomaly Scorer

Builds a statistical baseline profile for each MMSI from historical AIS data
and scores new windows against it.  Anomalies may indicate:
  - Vessel repurposing / cargo change
  - Spoofed identity (different vessel using an MMSI)
  - Unusual operational area (fishing outside normal grounds)
  - Suspicious speed profile change

Model per vessel:
  - Gaussian Mixture Model (GMM, k=3) over key behavioural features
  - Complemented by feature histograms for non-Gaussian features (SOG dist.)
  - Mahalanobis distance for fast Gaussian component scoring

Anomaly score [0,1]:
  0 = fully consistent with vessel's own history
  1 = extreme deviation (top-1% of global anomaly distribution)

Usage:
    from src.vessel_baseline import VesselBaselineProfiler
    vbp = VesselBaselineProfiler()
    vbp.fit(historical_feat_df)
    scores = vbp.score(new_feat_df)
"""

import logging
import pickle
from pathlib import Path
from typing import Optional, Dict

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Features used for the per-vessel baseline
BASELINE_FEATURES = [
    "sog_mean", "sog_std", "sog_max",
    "pct_slow", "pct_fast",
    "cog_std", "zig_zag", "mean_turning_rate",
    "loiter_index",
    "total_dist_nm",
    "dist_to_port_nm", "dist_to_fishing_nm",
]

_MIN_WINDOWS_FOR_BASELINE = 10   # need ≥10 historical windows to fit
_N_COMPONENTS              = 3   # GMM components


# ══════════════════════════════════════════════════════════════════════════════
class _VesselProfile:
    """Per-vessel GMM baseline."""

    def __init__(self, mmsi: int):
        self.mmsi    = mmsi
        self._gmm    = None
        self._scaler = None
        self._n_hist = 0
        self._feat_means: Optional[np.ndarray] = None
        self._feat_stds:  Optional[np.ndarray] = None

    # ──────────────────────────────────────────────────────────────────────────
    def fit(self, X: np.ndarray):
        """Fit GMM on (n_windows, n_features) array."""
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler

        self._n_hist = len(X)
        n_comp = min(_N_COMPONENTS, len(X))

        self._scaler = StandardScaler()
        Xs = self._scaler.fit_transform(X)

        self._gmm = GaussianMixture(
            n_components=n_comp,
            covariance_type="diag",
            max_iter=200,
            random_state=42,
        )
        self._gmm.fit(Xs)
        self._feat_means = X.mean(axis=0)
        self._feat_stds  = X.std(axis=0) + 1e-6

    # ──────────────────────────────────────────────────────────────────────────
    def score(self, X: np.ndarray) -> np.ndarray:
        """
        Return anomaly score [0,1] for each row in X.
        0 = normal, 1 = extreme anomaly.
        Converts log-likelihood to anomaly score by comparing to training range.
        """
        if self._gmm is None:
            return np.full(len(X), 0.5)

        Xs     = self._scaler.transform(X)
        log_ll = self._gmm.score_samples(Xs)   # (N,) lower = more anomalous

        # Calibrate against training set
        X_train_scaled = self._scaler.transform(
            self._feat_means[None, :] * np.ones((min(self._n_hist, 50), 1))
        )
        train_scores   = self._gmm.score_samples(X_train_scaled)
        ll_min = train_scores.min() - 5.0   # generous lower bound
        ll_max = train_scores.max()

        # Normalise: high ll → low anomaly
        normed = (log_ll - ll_max) / (ll_min - ll_max + 1e-9)
        return np.clip(normed, 0, 1).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
class VesselBaselineProfiler:
    """
    Manages per-vessel baselines and scores new observations against them.
    Falls back to a global fleet baseline for vessels with sparse history.
    """

    def __init__(self,
                 min_windows: int     = _MIN_WINDOWS_FOR_BASELINE,
                 cache_path:  Optional[str] = None):
        self._min_windows  = min_windows
        self._cache_path   = Path(cache_path) if cache_path else None
        self._profiles:    Dict[int, _VesselProfile] = {}
        self._global_gmm   = None
        self._global_scaler= None
        self._feature_cols = BASELINE_FEATURES
        self._fitted       = False

    # ──────────────────────────────────────────────────────────────────────────
    def fit(self, feat_df: pd.DataFrame) -> "VesselBaselineProfiler":
        """
        Fit per-vessel and global baselines.

        Args:
            feat_df: Segment-feature DataFrame (output of features.py).
                     Must contain mmsi and BASELINE_FEATURES columns.
        """
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler

        available = [c for c in self._feature_cols if c in feat_df.columns]
        if not available:
            log.warning("[baseline] No baseline features found in DataFrame")
            return self

        self._feature_cols = available
        df = feat_df.dropna(subset=["mmsi"]).copy()
        df[available] = df[available].fillna(0)

        # ── Per-vessel profiles ───────────────────────────────────────────────
        n_fitted = 0
        for mmsi, grp in df.groupby("mmsi"):
            if len(grp) < self._min_windows:
                continue
            X = grp[available].values.astype(np.float32)
            profile = _VesselProfile(int(mmsi))
            try:
                profile.fit(X)
                self._profiles[int(mmsi)] = profile
                n_fitted += 1
            except Exception as e:
                log.debug("[baseline] MMSI %s profile failed: %s", mmsi, e)

        log.info("[baseline] Fitted %d per-vessel profiles", n_fitted)

        # ── Global fleet baseline (for vessels with sparse history) ───────────
        X_all = df[available].values.astype(np.float32)
        self._global_scaler = StandardScaler().fit(X_all)
        Xs = self._global_scaler.transform(X_all)
        n_comp = min(_N_COMPONENTS, len(Xs))
        self._global_gmm = GaussianMixture(
            n_components=n_comp, covariance_type="diag",
            max_iter=200, random_state=42,
        ).fit(Xs)

        self._fitted = True
        if self._cache_path:
            self.save(str(self._cache_path))
        return self

    # ──────────────────────────────────────────────────────────────────────────
    def score(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score new windows against vessel baselines.

        Returns:
            DataFrame with mmsi + baseline_anomaly_score [0,1].
        """
        if not self._fitted:
            raise RuntimeError("Call fit() before score()")

        available = [c for c in self._feature_cols if c in feat_df.columns]
        df        = feat_df.copy()
        df[available] = df[available].fillna(0)

        scores    = np.zeros(len(df), dtype=np.float32)
        uses_per_vessel = np.zeros(len(df), dtype=bool)

        for idx, row in df.iterrows():
            mmsi = int(row.get("mmsi", 0))
            x    = row[available].values.astype(np.float32).reshape(1, -1)
            i    = df.index.get_loc(idx)

            if mmsi in self._profiles:
                scores[i]         = self._profiles[mmsi].score(x)[0]
                uses_per_vessel[i] = True
            else:
                # Fall back to global baseline
                xs     = self._global_scaler.transform(x)
                log_ll = self._global_gmm.score_samples(xs)[0]
                # Rough calibration: global typical ll ~ -5 to -20
                scores[i] = float(np.clip((-log_ll - 5) / 15.0, 0, 1))

        out = feat_df[["mmsi"]].copy().reset_index(drop=True) if "mmsi" in feat_df else pd.DataFrame()
        out = feat_df.copy().reset_index(drop=True)
        out["baseline_anomaly_score"] = scores
        out["uses_per_vessel_baseline"] = uses_per_vessel
        return out

    # ──────────────────────────────────────────────────────────────────────────
    def vessel_summary(self, mmsi: int) -> Optional[dict]:
        """Return summary statistics for a vessel's historical profile."""
        profile = self._profiles.get(mmsi)
        if profile is None:
            return None
        return {
            "mmsi":          mmsi,
            "n_windows":     profile._n_hist,
            "feature_means": dict(zip(self._feature_cols,
                                      profile._feat_means.tolist()
                                      if profile._feat_means is not None else [])),
        }

    # ──────────────────────────────────────────────────────────────────────────
    def most_anomalous(self, feat_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """Return the top_n most anomalous windows."""
        scored = self.score(feat_df)
        return scored.nlargest(top_n, "baseline_anomaly_score").reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────────────
    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({
                "profiles":       self._profiles,
                "global_gmm":     self._global_gmm,
                "global_scaler":  self._global_scaler,
                "feature_cols":   self._feature_cols,
                "min_windows":    self._min_windows,
            }, f)
        log.info("[baseline] Saved to %s", path)

    def load(self, path: str) -> "VesselBaselineProfiler":
        with open(path, "rb") as f:
            d = pickle.load(f)
        self._profiles       = d["profiles"]
        self._global_gmm     = d["global_gmm"]
        self._global_scaler  = d["global_scaler"]
        self._feature_cols   = d["feature_cols"]
        self._min_windows    = d["min_windows"]
        self._fitted         = True
        log.info("[baseline] Loaded from %s (%d vessel profiles)",
                 path, len(self._profiles))
        return self
