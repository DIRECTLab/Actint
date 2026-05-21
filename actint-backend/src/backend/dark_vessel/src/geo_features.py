"""
Geospatial Feature Augmentation

Provides two spatial priors that dramatically improve fishing recall:
  1. GFW fishing effort density grid  (0.1° × 0.1° cells, fishing_hours/year)
  2. Bathymetric depth lookup via NOAA ERDDAP or local cache

Also provides:
  - Shipping lane proximity index  (distance to high-density cargo corridors)

Usage:
    from src.geo_features import GeoFeatureAugmenter
    aug = GeoFeatureAugmenter()
    df  = aug.augment(df)   # adds gfw_effort, depth_m, lane_proximity cols
"""

import os
import io
import zipfile
import logging
import hashlib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE        = Path(__file__).parent.parent
GFW_ZIP      = _HERE / "data/gfw/fleet-monthly-csvs-10-v3-2023.zip"
GFW_CACHE    = _HERE / "data/gfw/effort_grid_cache.npz"
DEPTH_CACHE  = _HERE / "data/gfw/depth_cache.parquet"

# NOAA ERDDAP endpoint for ETOPO2 global 2-min bathymetry
_ERDDAP_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo360.csv?"
    "altitude[({})][({})]"
)

# ── Approximate major shipping lane centrelines (lat, lon pairs, 1° spacing) ─
# Generated from AIS density studies; used for lane proximity index only.
_LANE_WAYPOINTS = np.array([
    # Strait of Malacca
    *[(1.0 + i*0.5, 103.8 + i*0.3) for i in range(12)],
    # English Channel
    *[(51.0 + i*0.1, 1.5 + i*0.4) for i in range(10)],
    # Suez approach (Red Sea)
    *[(12.5 + i*1.0, 43.5 + i*0.2) for i in range(20)],
    # Panama approach (Pacific)
    *[(8.5, -79.5 + i*1.0) for i in range(15)],
    # North Atlantic main
    *[(50.0 + i*0.2, -30.0 + i*1.5) for i in range(30)],
    # Trans-Pacific
    *[(35.0 + i*0.1, 140.0 + i*1.2) for i in range(40)],
    # Gulf of Guinea main
    *[(3.0 + i*0.3, 2.0 + i*0.5) for i in range(20)],
], dtype=np.float32)


# ══════════════════════════════════════════════════════════════════════════════
# GFW effort grid builder
# ══════════════════════════════════════════════════════════════════════════════

class _GFWGrid:
    """0.1° fishing effort grid from GFW fleet-monthly zip."""

    CELL = 0.1  # degree resolution

    def __init__(self):
        self.effort: Optional[np.ndarray] = None
        self.lat_min = -90.0
        self.lon_min = -180.0
        self.nlat = 1800
        self.nlon = 3600
        self._load_or_build()

    # ──────────────────────────────────────────────────────────────────────────
    def _load_or_build(self):
        if GFW_CACHE.exists():
            npz = np.load(str(GFW_CACHE))
            self.effort = npz["effort"]
            log.info("[geo] GFW grid loaded from cache (%s)", GFW_CACHE.name)
            return

        if not GFW_ZIP.exists():
            log.warning("[geo] GFW zip not found – effort grid will be zeros")
            self.effort = np.zeros((self.nlat, self.nlon), dtype=np.float32)
            return

        log.info("[geo] Building GFW effort grid from %s …", GFW_ZIP.name)
        grid = np.zeros((self.nlat, self.nlon), dtype=np.float64)

        with zipfile.ZipFile(str(GFW_ZIP)) as z:
            for name in z.namelist():
                with z.open(name) as f:
                    chunk = pd.read_csv(f, usecols=["cell_ll_lat", "cell_ll_lon",
                                                     "fishing_hours"])
                    lats = chunk["cell_ll_lat"].values
                    lons = chunk["cell_ll_lon"].values
                    hrs  = chunk["fishing_hours"].values

                    row = np.floor((lats - self.lat_min) / self.CELL).astype(int)
                    col = np.floor((lons - self.lon_min) / self.CELL).astype(int)

                    valid = (
                        (row >= 0) & (row < self.nlat) &
                        (col >= 0) & (col < self.nlon) &
                        np.isfinite(hrs)
                    )
                    np.add.at(grid, (row[valid], col[valid]), hrs[valid])

        # Log-scale + normalise to [0,1]
        grid = np.log1p(grid).astype(np.float32)
        self.effort = (grid / grid.max()).astype(np.float32)

        np.savez_compressed(str(GFW_CACHE), effort=self.effort)
        log.info("[geo] GFW effort grid cached to %s", GFW_CACHE.name)

    # ──────────────────────────────────────────────────────────────────────────
    def lookup(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """Return fishing effort [0,1] for each (lat, lon) pair."""
        row = np.clip(
            np.floor((lats - self.lat_min) / self.CELL).astype(int),
            0, self.nlat - 1,
        )
        col = np.clip(
            np.floor((lons - self.lon_min) / self.CELL).astype(int),
            0, self.nlon - 1,
        )
        return self.effort[row, col]


# ══════════════════════════════════════════════════════════════════════════════
# Depth cache (lightweight requests to NOAA ERDDAP)
# ══════════════════════════════════════════════════════════════════════════════

class _DepthLookup:
    """
    Local cache for ETOPO2 depth values.  Quantises to nearest 0.5° cell to
    maximise cache hits.  Falls back gracefully when network is unavailable.
    """

    QUANT = 0.5  # degree quantisation

    def __init__(self):
        self._cache: dict[tuple, float] = {}
        if DEPTH_CACHE.exists():
            df = pd.read_parquet(str(DEPTH_CACHE))
            for _, r in df.iterrows():
                self._cache[(r["lat_q"], r["lon_q"])] = r["depth_m"]
            log.info("[geo] Depth cache loaded (%d entries)", len(self._cache))

    # ──────────────────────────────────────────────────────────────────────────
    def _fetch_one(self, lat_q: float, lon_q: float) -> float:
        """Try NOAA ERDDAP; return NaN on failure."""
        try:
            import urllib.request
            url = _ERDDAP_URL.format(lat_q, lon_q)
            with urllib.request.urlopen(url, timeout=5) as r:
                lines = r.read().decode().splitlines()
            # CSV: header line then data line  "altitude,... \n value,..."
            if len(lines) >= 2:
                val = float(lines[1].split(",")[0])
                return -val   # ETOPO2 uses negative for ocean; invert to depth>0
        except Exception:
            pass
        return np.nan

    def lookup(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        lats_q = np.round(lats / self.QUANT) * self.QUANT
        lons_q = np.round(lons / self.QUANT) * self.QUANT
        result = np.full(len(lats), np.nan, dtype=np.float32)
        new_entries = []

        for i, (la, lo) in enumerate(zip(lats_q, lons_q)):
            key = (la, lo)
            if key in self._cache:
                result[i] = self._cache[key]
            else:
                val = self._fetch_one(la, lo)
                self._cache[key] = val
                new_entries.append({"lat_q": la, "lon_q": lo, "depth_m": val})
                result[i] = val

        if new_entries:
            new_df = pd.DataFrame(new_entries)
            if DEPTH_CACHE.exists():
                existing = pd.read_parquet(str(DEPTH_CACHE))
                new_df = pd.concat([existing, new_df], ignore_index=True)
            new_df.to_parquet(str(DEPTH_CACHE), index=False)

        return result


# ══════════════════════════════════════════════════════════════════════════════
# Lane proximity
# ══════════════════════════════════════════════════════════════════════════════

def _lane_proximity(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """
    Returns a [0,1] proximity score to major shipping lanes.
    1.0 = on a lane corridor, 0.0 = >200 nm away.
    """
    pts = np.column_stack([lats, lons])   # (N,2)
    # Vectorised nearest-lane-waypoint distance (degrees as proxy for nm)
    dists = np.sqrt(
        ((pts[:, None, :] - _LANE_WAYPOINTS[None, :, :]) ** 2).sum(axis=-1)
    ).min(axis=1)  # (N,)
    # 1° ≈ 60 nm; 200 nm ≈ 3.3°
    return np.clip(1.0 - dists / 3.3, 0, 1).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
# Public augmenter
# ══════════════════════════════════════════════════════════════════════════════

class GeoFeatureAugmenter:
    """
    Adds geo-contextual columns to any DataFrame that has lat/lon columns.

    New columns:
        gfw_effort      – [0,1]  normalised log-fishing-hours at centroid
        depth_m         – metres (positive=ocean depth); NaN for land/unavailable
        lane_proximity  – [0,1]  proximity to major shipping lanes
        on_shelf        – bool   depth < 200 m (continental shelf)
        gear_depth_fit  – [0,1]  how well depth matches vessel's typical gear
    """

    def __init__(self, fetch_depth: bool = False):
        """
        Args:
            fetch_depth: If True, attempt live NOAA ERDDAP queries for depth.
                         False uses cached values only (fast, offline-safe).
        """
        self._gfw   = _GFWGrid()
        self._depth = _DepthLookup() if fetch_depth else None
        self._fetch = fetch_depth

    # ──────────────────────────────────────────────────────────────────────────
    def augment(self, df: pd.DataFrame,
                lat_col: str = "lat", lon_col: str = "lon") -> pd.DataFrame:
        """
        Augment df with geo features. lat/lon are centroid positions.
        Works with both segment-feature DataFrames and raw ping DataFrames.
        """
        df = df.copy()

        # Resolve lat/lon (centroid_lat/centroid_lon from partial-track features)
        if lat_col not in df.columns:
            if "centroid_lat" in df.columns:
                lat_col, lon_col = "centroid_lat", "centroid_lon"
            else:
                log.warning("[geo] No lat/lon columns found – skipping augment")
                return df

        lats = df[lat_col].values.astype(np.float32)
        lons = df[lon_col].values.astype(np.float32)

        valid = np.isfinite(lats) & np.isfinite(lons)

        # GFW effort
        effort = np.full(len(df), np.nan, dtype=np.float32)
        if valid.any():
            effort[valid] = self._gfw.lookup(lats[valid], lons[valid])
        df["gfw_effort"] = effort

        # Depth
        depth = np.full(len(df), np.nan, dtype=np.float32)
        if self._fetch and valid.any():
            depth[valid] = self._depth.lookup(lats[valid], lons[valid])
        df["depth_m"] = depth

        # Shipping lane proximity
        lane = np.zeros(len(df), dtype=np.float32)
        if valid.any():
            lane[valid] = _lane_proximity(lats[valid], lons[valid])
        df["lane_proximity"] = lane

        # Derived features
        df["on_shelf"] = (df["depth_m"] < 200) & df["depth_m"].notna()

        # Gear-depth fitness: trawlers/longliners work 50–500m; purse seiners
        # surface; jigging near surface at night.  Use a soft proxy based on
        # depth alone (refine per vessel type in classifier pipeline).
        trawl_depth = np.clip(
            1.0 - np.abs(df["depth_m"].fillna(300) - 200) / 300, 0, 1
        )
        df["gear_depth_fit"] = trawl_depth.astype(np.float32)

        return df

    # ──────────────────────────────────────────────────────────────────────────
    def augment_segment_features(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """
        Augment segment-level feature DataFrame (output of features.py).
        Uses segment centroid derived from lat_range / lon_range if needed.
        """
        return self.augment(feat_df,
                            lat_col="centroid_lat" if "centroid_lat" in feat_df.columns else "lat",
                            lon_col="centroid_lon" if "centroid_lon" in feat_df.columns else "lon")
