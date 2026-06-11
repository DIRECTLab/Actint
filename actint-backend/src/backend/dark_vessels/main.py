"""
Activity Intelligence Engine — Main Runner

Usage:
    python main.py                         # run all regions
    python main.py --region brazil_eez     # single region
    python main.py --region philippines_eez --vessels 40
    python main.py --list-regions
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine

import pandas as pd
import numpy as np

from colorama import Fore

from backend.dark_vessels.src.simulator import simulate_region
from backend.dark_vessels.src.sequence_classifier import SequenceClassifier
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_position_history_helper, get_all_mmsis

# ── project imports ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from backend.dark_vessels.src.simulation.simulator        import simulate_region
from backend.dark_vessels.src.feature_extraction.features         import compute_vessel_features, compute_segment_features
from backend.dark_vessels.src.classifiers.classifier       import ActivityIntelligenceClassifier
from backend.dark_vessels.src.anomaly_detection.dark_vessel_detector import DarkVesselDetector
from backend.dark_vessels.src.util.visualizer       import (
    build_region_map,
    plot_activity_distribution,
    plot_confusion_matrix,
    plot_feature_importance,
    plot_speed_profiles,
)
from backend.dark_vessels.src.real_data_helpers.real_data_viz import (
    build_real_fishing_map,
    plot_real_fleet_composition,
    plot_model_vs_reality,
    print_region_intelligence_report,
)
from backend.dark_vessels.src.real_data_helpers.real_ais_validator import validate_real_ais
from backend.dark_vessels.src.classifiers.partial_track_classifier import (
    PartialTrackClassifier, build_training_data, PARTIAL_FEATURES,
    UNIFIED_VESSEL_TYPES, ACTIVITY_LABELS,
)
from src.real_ais_loader import load_ais_file
from src.regions import REGIONS
from src.geo_features import GeoFeatureAugmenter
from src.rendezvous_detector import RendezvousDetector
from src.dark_period_predictor import DarkPeriodPredictor, VesselState
from src.vessel_baseline import VesselBaselineProfiler
from backend.config import config

out_dir = Path("outputs")
OUTPUT_DIR = Path("outputs")

db_url = (
    f"postgresql+psycopg2://"
    f"{config.DB_USER}:{config.DB_PASS}"
    f"@{config.DB_HOST}:{config.DB_PORT}"
    f"/{config.FISHY_REPORTS_DB_NAME}"
)

engine = create_engine(db_url)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: pretty print table
# ─────────────────────────────────────────────────────────────────────────────

def _print_table(df: pd.DataFrame, cols: list, title: str, n: int = 20):
    print(f"\n{'─'*80}")
    print(f"  {title}")
    print(f"{'─'*80}")
    sub = df[cols].head(n)
    # Right-pad/truncate strings
    col_widths = {}
    for c in cols:
        col_widths[c] = max(len(str(c)), sub[c].astype(str).str.len().max())
        col_widths[c] = min(col_widths[c], 22)

    header = "  ".join(str(c).ljust(col_widths[c]) for c in cols)
    print(header)
    print("  ".join("─" * col_widths[c] for c in cols))
    for _, row in sub.iterrows():
        print("  ".join(str(row[c])[:col_widths[c]].ljust(col_widths[c]) for c in cols))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline for one region
# ─────────────────────────────────────────────────────────────────────────────

def run_region(region_key: str, n_fishing: int = 20, n_cargo: int = 12, visualise: bool = False) -> dict:
    region_name = REGIONS[region_key]["name"]
    print(f"\n{'═'*80}")
    print(f"  ACTIVITY INTELLIGENCE ENGINE — {region_name.upper()}")
    print(f"{'═'*80}")

    # ── 1. Simulate AIS data ─────────────────────────────────────────────────
    print("\n[1/6] Simulating AIS vessel tracks ...")
    raw_df = simulate_region(region_key)
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
    n_vessels  = raw_df["mmsi"].nunique()
    n_pings    = len(raw_df)
    dark_pings = int((~raw_df["ais_on"]).sum())
    print(f"      {n_vessels} vessels  |  {n_pings:,} AIS pings  |  "
          f"{dark_pings:,} dark pings ({dark_pings/n_pings:.1%})")

    # ── 2. Feature engineering ───────────────────────────────────────────────
    print("[2/6] Computing segment features (sliding window) ...")
    # Segment-level (20-ping windows, step 10) for classifier training/eval
    seg_df  = compute_segment_features(raw_df, region_key=region_key,
                                        window_size=20, step_size=10)
    # Vessel-level for dark detection and summary
    feat_df = compute_vessel_features(raw_df, region_key=region_key)
    print(f"      {len(seg_df):,} segments  |  {len(feat_df)} vessels  |  "
          f"{len(seg_df.columns)} features")

    # ── 3. Train & evaluate classifier ──────────────────────────────────────
    print("[3/6] Training activity classifier on segments ...")
    # Train/test split: 70% train, 30% test (by vessel, not by ping, to avoid leakage)
    all_mmsis = seg_df["mmsi"].unique()
    RNG_eval  = np.random.default_rng(99)
    RNG_eval.shuffle(all_mmsis)
    split_idx = int(len(all_mmsis) * 0.7)
    train_mmsis = set(all_mmsis[:split_idx])
    test_mmsis  = set(all_mmsis[split_idx:])

    train_seg = seg_df[seg_df["mmsi"].isin(train_mmsis)]
    test_seg  = seg_df[seg_df["mmsi"].isin(test_mmsis)]

    clf = ActivityIntelligenceClassifier()
    clf.fit(train_seg)
    eval_results = clf.evaluate(test_seg)

    report = eval_results["classification_report"]
    macro_f1 = report.get("macro avg", {}).get("f1-score", 0)
    weighted_f1 = report.get("weighted avg", {}).get("f1-score", 0)
    print(f"      Train vessels: {len(train_mmsis)}  |  Test vessels: {len(test_mmsis)}")
    print(f"      Train segs:    {len(train_seg):,}  |  Test segs:    {len(test_seg):,}")
    print(f"      Macro F1:    {macro_f1:.3f}")
    print(f"      Weighted F1: {weighted_f1:.3f}")

    # Per-class accuracy
    print("\n      Per-class metrics:")
    for label in eval_results["labels"]:
        if label in report and isinstance(report[label], dict):
            r = report[label]
            print(f"        {label:<12}  P={r['precision']:.2f}  R={r['recall']:.2f}  "
                  f"F1={r['f1-score']:.2f}  support={r['support']}")

    # ── 4. Predict on full dataset ───────────────────────────────────────────
    print("\n[4/6] Running predictions on segments + vessel roll-up ...")
    # Segment-level predictions
    seg_preds = clf.predict(seg_df)
    seg_preds["mmsi"] = seg_df["mmsi"].values

    # Roll up segment predictions to vessel level (majority vote + max risk)
    vessel_rollup = (
        seg_preds.groupby("mmsi")
        .agg(
            pred_activity        = ("pred_activity", lambda x: x.mode().iloc[0]),
            pred_vessel_type     = ("pred_vessel_type", lambda x: x.mode().iloc[0]),
            activity_confidence  = ("activity_confidence", "mean"),
            vessel_confidence    = ("vessel_confidence", "mean"),
            dark_vessel_risk     = ("dark_vessel_risk", "max"),
            iuu_fishing_risk     = ("iuu_fishing_risk", "max"),
            sts_evasion_risk     = ("sts_evasion_risk", "max"),
            overall_anomaly_score= ("overall_anomaly_score", "max"),
        )
        .reset_index()
    )
    # Merge name/flag from feat_df
    vessel_rollup = vessel_rollup.merge(
        feat_df[["mmsi", "name", "flag"]], on="mmsi", how="left"
    )
    vessel_rollup["pred_activity_label"] = vessel_rollup["pred_activity"].map(
        lambda x: {"fishing":"Fishing","transit":"Transit","anchored":"Anchored/Moored",
                   "loiter":"Loitering","sts":"STS Transfer","port":"In Port"}.get(x, x))
    vessel_rollup["pred_vessel_label"] = vessel_rollup["pred_vessel_type"].map(
        lambda x: {"trawler":"Fishing - Trawler","longliner":"Fishing - Longliner",
                   "purse_seiner":"Fishing - Purse Seiner","cargo":"Cargo",
                   "tanker":"Tanker","bulk_carrier":"Bulk Carrier",
                   "naval":"Naval/Patrol","support_vessel":"Offshore Support"}.get(x, x))
    results_df = vessel_rollup

    high_risk = results_df[results_df["overall_anomaly_score"] > 0.5]
    print(f"      High-risk vessels (score > 0.5): {len(high_risk)}")

    # ── 5. Dark vessel analysis ──────────────────────────────────────────────
    print("[5/6] Dark vessel detection ...")
    detector = DarkVesselDetector()
    dark_df  = detector.analyze_fleet(raw_df)
    spoofed_mmsis = detector.detect_mmsi_clones(raw_df)

    n_dark_flagged = int((dark_df["dark_risk_score"] > 0.3).sum())
    print(f"      Vessels with dark risk > 0.3: {n_dark_flagged}")
    print(f"      Suspected MMSI clones:         {len(spoofed_mmsis)}")

    # ── 6. Output ────────────────────────────────────────────────────────────
    print("[6/6] Generating outputs ...")

    # Save to PostgreSQL
    raw_df.to_sql("raw_tracks", engine, if_exists="replace", index=False)
    feat_df.to_sql("features", engine, if_exists="replace", index=False)
    seg_df.to_sql("segments", engine, if_exists="replace", index=False)
    seg_preds.to_sql("segment_predictions", engine, if_exists="replace", index=False)
    results_df.to_sql("predictions", engine, if_exists="replace", index=False)
    dark_df.to_sql("dark_analysis", engine, if_exists="replace", index=False)

    # Charts
    map_path = build_region_map(
        raw_df, results_df, dark_df, region_key,
        str(out_dir / "map.html")
    )
    print(f"      Interactive map: {map_path}")

    if visualise:
        plot_activity_distribution(
            results_df, region_key,
            str(out_dir / "activity_distribution.png")
        )
        plot_confusion_matrix(
            eval_results["confusion_matrix"],
            eval_results["labels"],
            region_key,
            str(out_dir / "confusion_matrix.png")
        )
        plot_feature_importance(
            eval_results["feature_importance"],
            region_key,
            str(out_dir / "feature_importance.png")
        )
        plot_speed_profiles(
            raw_df, region_key,
            str(out_dir / "speed_profiles.png")
        )

        # Real data integration (GFW 2023)
        try:
            real_map = build_real_fishing_map(
                region_key, str(out_dir / "real_fishing_map.html"))
            plot_real_fleet_composition(
                region_key, str(out_dir / "real_fleet_composition.png"))
            plot_model_vs_reality(
                region_key, results_df, str(out_dir / "model_vs_reality.png"))
            print_region_intelligence_report(region_key)
            print(f"      Real-data map:   {real_map}")
        except FileNotFoundError as e:
            print(f"      [skipping real data: {e}]")

    # ── Console summary tables ────────────────────────────────────────────────
        # Merge results with dark scores
        summary = results_df.merge(
            dark_df[["mmsi", "dark_risk_score", "anomaly_flags", "max_gap_h"]],
            on="mmsi", how="left"
        )
        
        _print_table(
            summary.sort_values("overall_anomaly_score", ascending=False),
            cols=["mmsi", "name", "flag", "pred_vessel_label",
                "pred_activity_label", "activity_confidence",
                "dark_risk_score", "iuu_fishing_risk", "sts_evasion_risk"],
            title=f"ALL VESSELS — Ranked by Anomaly Score ({region_name})",
            n=30,
        )

        flagged = summary[summary["anomaly_flags"] != "NONE"].sort_values(
            "dark_risk_score", ascending=False)
        if not flagged.empty:
            _print_table(
                flagged,
                cols=["mmsi", "name", "flag", "pred_activity_label",
                    "dark_risk_score", "anomaly_flags"],
                title=f"FLAGGED ANOMALOUS VESSELS ({region_name})",
                n=20,
            )

    # ── Console summary tables ────────────────────────────────────────────────
    # Merge results with dark scores
    summary = results_df.merge(
        dark_df[["mmsi", "dark_risk_score", "anomaly_flags", "max_gap_h"]],
        on="mmsi", how="left"
    )

    # ── Algorithm performance summary ────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  ALGORITHM PERFORMANCE — {region_name}")
    print(f"{'─'*80}")
    print(f"  Simulated vessels:     {n_vessels}")
    print(f"  Total AIS pings:       {n_pings:,}")
    print(f"  Dark fraction:         {dark_pings/n_pings:.1%}")
    print(f"  Activity F1 (macro):   {macro_f1:.3f}")
    print(f"  Activity F1 (weighted):{weighted_f1:.3f}")
    print(f"  Dark vessel detections:{n_dark_flagged}")
    print(f"  High-risk vessels:     {len(high_risk)}")
    print(f"  Output dir:            {out_dir}/")
    print()

    return {
        "region": region_key,
        "n_vessels": n_vessels,
        "n_pings": n_pings,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "dark_fraction": dark_pings / n_pings,
        "n_dark_flagged": n_dark_flagged,
        "n_high_risk": len(high_risk),
        "output_dir": str(out_dir),
        "map_path": map_path,
        "classification_report": report,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Partial track training + evaluation
# ─────────────────────────────────────────────────────────────────────────────

def run_partial_track_training(
    ais_files: list,
    source: str = "noaa",
    max_rows_per_file: int = 1_000_000,
    max_vessels_per_file: int = 2000,
    output_dir: str = "outputs/partial_track",
    model_save_path: str = "outputs/partial_track/model.pkl",
) -> dict:
    """
    Train and evaluate the PartialTrackClassifier on real AIS data.

    Strategy:
      1. Load each AIS file, subsample to max_vessels_per_file
      2. Build training examples at N = 1, 2, 3, 5, 8, 10, 15, 20, 30, 50 pings
      3. Train on 70% of vessels, test on 30%
      4. Report F1 at each track length (shows how accuracy degrades with fewer obs)
    """
    from backend.dark_vessels.src.util.gpu_utils import compute_device, BACKEND
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*80}")
    print(f"  PARTIAL TRACK CLASSIFIER — Training")
    print(f"  Backend: {BACKEND}  |  Device: {compute_device}")
    print(f"{'═'*80}")

    all_dfs = []
    for fpath in ais_files:
        print(f"\n  Loading {Path(fpath).name} ...")
        df = load_ais_file(fpath, source=source, max_rows=max_rows_per_file)
        # Subsample vessels
        mmsis = df["mmsi"].unique()
        if len(mmsis) > max_vessels_per_file:
            rng  = np.random.default_rng(42)
            mmsis = rng.choice(mmsis, max_vessels_per_file, replace=False)
            df = df[df["mmsi"].isin(mmsis)]
        # Drop short tracks
        counts = df["mmsi"].value_counts()
        df = df[df["mmsi"].isin(counts[counts >= 10].index)]
        print(f"      {df['mmsi'].nunique()} vessels  |  {len(df):,} pings")
        all_dfs.append(df)

    if not all_dfs:
        print("No data loaded.")
        return {}

    full_df = pd.concat(all_dfs, ignore_index=True)
    print(f"\n  Combined: {full_df['mmsi'].nunique():,} vessels  |  {len(full_df):,} pings")

    # Train/test split by vessel
    all_mmsis = np.array(full_df["mmsi"].unique())
    rng = np.random.default_rng(42)
    rng.shuffle(all_mmsis)
    split = int(len(all_mmsis) * 0.70)
    train_mmsis = set(all_mmsis[:split])
    test_mmsis  = set(all_mmsis[split:])

    train_df = full_df[full_df["mmsi"].isin(train_mmsis)].copy()
    test_df  = full_df[full_df["mmsi"].isin(test_mmsis)].copy()

    n_lengths = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50]

    print(f"\n  Building training data at N = {n_lengths} pings ...")
    train_feat = build_training_data(train_df, source, n_lengths, n_jobs=-1)
    print(f"  Training examples: {len(train_feat):,}")

    print("  Building test data ...")
    test_feat  = build_training_data(test_df,  source, n_lengths, n_jobs=-1)
    print(f"  Test examples:     {len(test_feat):,}")

    print("\n  Training classifier (GPU XGBoost) ...")
    clf = PartialTrackClassifier()
    clf.fit(train_feat)

    print("  Evaluating ...")
    results = clf.evaluate(test_feat, by_n_obs=True)

    # Print results
    print(f"\n{'═'*80}")
    print("  PARTIAL TRACK CLASSIFIER — Results")
    print(f"{'═'*80}")
    print(f"  Activity  F1 macro:    {results.get('activity_f1_macro', 0):.3f}")
    print(f"  Activity  F1 weighted: {results.get('activity_f1_weighted', 0):.3f}")
    print(f"  Vess.type F1 macro:    {results.get('vtype_f1_macro', 0):.3f}")
    print(f"  Vess.type F1 weighted: {results.get('vtype_f1_weighted', 0):.3f}")

    by_n = results.get("activity_f1_by_n_obs", {})
    if by_n:
        print(f"\n  Activity F1 by track length:")
        for n_obs in sorted(by_n):
            bar = "█" * int(by_n[n_obs] * 40)
            print(f"    N={n_obs:>3} pings  {bar:<40}  F1={by_n[n_obs]:.3f}")

    # Per-class breakdown
    act_report = results.get("activity_report", {})
    if act_report:
        print(f"\n  Per-class activity performance:")
        for label in ACTIVITY_LABELS:
            r = act_report.get(label, {})
            if isinstance(r, dict) and r.get("support", 0) > 0:
                print(f"    {label:<14}  P={r.get('precision',0):.2f}  "
                      f"R={r.get('recall',0):.2f}  "
                      f"F1={r.get('f1-score',0):.2f}  "
                      f"n={int(r.get('support',0))}")

    vt_report = results.get("vtype_report", {})
    if vt_report:
        print(f"\n  Per-class vessel type performance:")
        for vtype in UNIFIED_VESSEL_TYPES:
            r = vt_report.get(vtype, {})
            if isinstance(r, dict) and r.get("support", 0) > 0:
                print(f"    {vtype:<18}  P={r.get('precision',0):.2f}  "
                      f"R={r.get('recall',0):.2f}  "
                      f"F1={r.get('f1-score',0):.2f}  "
                      f"n={int(r.get('support',0))}")

    # Save model
    clf.save(model_save_path)
    print(f"\n  Model saved: {model_save_path}")

    # Demo: single-observation predictions
    print(f"\n{'─'*80}")
    print("  DEMO — Single-Observation Predictions (EO satellite pass)")
    print(f"{'─'*80}")
    demos = [
        # (lat, lon, sog, heading, vessel_type, sensor, nav_status, note)
        dict(lat=1.2,  lon=104.0, sog=2.1,  heading=45,  vessel_type=None,      nav_status=None, sensor="eo",    note="Malacca — slow, unknown type"),
        dict(lat=1.5,  lon=103.8, sog=14.5, heading=270, vessel_type="cargo",   nav_status=0,    sensor="radar", note="Malacca — fast cargo transit"),
        dict(lat=4.0,  lon=100.5, sog=0.2,  heading=180, vessel_type="tanker",  nav_status=5,    sensor="sar",   note="Moored tanker, SAR image"),
        dict(lat=25.0, lon=57.0,  sog=8.0,  heading=0,   vessel_type=None,      nav_status=None, sensor="ais",   note="Persian Gulf, no type, 5 pings"),
        dict(lat=-8.4, lon=-35.0, sog=3.0,  heading=90,  vessel_type="fishing", nav_status=7,    sensor="eo",    note="Brazil coast — fishing"),
        dict(lat=4.2,  lon=-7.1,  sog=1.2,  heading=210, vessel_type=None,      nav_status=None, sensor="sar",   note="Gulf of Guinea — slow, dark"),
        dict(lat=14.5, lon=120.0, sog=12.0, heading=195, vessel_type="cargo",   nav_status=0,    sensor="ais",   note="Philippines strait — cargo"),
    ]
    for d in demos:
        r = clf.predict_single(
            lat=d["lat"], lon=d["lon"],
            sog=d.get("sog"), heading=d.get("heading"),
            vessel_type=d.get("vessel_type"),
            nav_status=d.get("nav_status"),
            sensor_type=d["sensor"],
        )
        # Top-2 activity probabilities
        act_proba = sorted(r.get("activity_proba", {}).items(), key=lambda x: -x[1])[:2]
        top2 = "  ".join(f"{a}:{p:.2f}" for a, p in act_proba)
        print(f"  ({d['lat']:>6.1f}°, {d['lon']:>7.1f}°)  sog={d.get('sog','?'):>5}kn  "
              f"sensor={d['sensor']:<13}"
              f"→ {r['activity']:<10}  {r['vessel_type']:<16}  "
              f"conf={r['confidence']:.2f}   [{top2}]   {d['note']}")

    train_feat.to_csv(out_dir / "train_features.csv", index=False)
    test_feat.to_csv(out_dir / "test_features.csv",  index=False)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Multi-region comparison
# ─────────────────────────────────────────────────────────────────────────────

def compare_regions(region_keys: list) -> None:
    results = []
    for rk in region_keys:
        r = run_region(rk)
        results.append(r)

    print(f"\n{'═'*80}")
    print("  CROSS-REGION ALGORITHM PERFORMANCE COMPARISON")
    print(f"{'═'*80}")
    print(f"  {'Region':<28} {'F1 Macro':>9} {'F1 Weighted':>12} "
          f"{'Dark%':>7} {'Dark Flagged':>13} {'High Risk':>10}")
    print(f"  {'─'*28} {'─'*9} {'─'*12} {'─'*7} {'─'*13} {'─'*10}")
    for r in results:
        print(f"  {r['region']:<28} "
              f"{r['macro_f1']:>9.3f} "
              f"{r['weighted_f1']:>12.3f} "
              f"{r['dark_fraction']:>7.1%} "
              f"{r['n_dark_flagged']:>13} "
              f"{r['n_high_risk']:>10}")
    print()

    # Save comparison JSON
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "region_comparison.json", "w") as f:
        # Make JSON-serialisable
        clean = [{k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                  for k, v in r.items() if k != "classification_report"}
                 for r in results]
        json.dump(clean, f, indent=2)
    print(f"  Comparison saved to {OUTPUT_DIR / 'region_comparison.json'}")


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced intelligence pipeline (all new modules)
# ─────────────────────────────────────────────────────────────────────────────

def run_enhanced_intelligence(
    ais_path: str,
    source: str            = "auto",
    max_rows: int          = 2_000_000,
    max_vessels: int       = 1000,
    bbox                   = None,
    output_dir             = None,
) -> dict:
    """
    Full enhanced Activity Intelligence pipeline:
      1. Load + normalise AIS
      2. Geo-feature augmentation (GFW fishing effort + shipping lane proximity)
      3. Segment-level XGBoost classification
      4. Per-vessel behavioural baseline + anomaly scoring
      5. Rendezvous / proximity event detection
      6. Dark-period dead-reckoning for top-risk vessels

    Returns a summary dict suitable for downstream reporting.
    """
    from src.real_ais_loader import load_ais_file
    from src.features import compute_segment_features

    out_dir = Path(output_dir) if output_dir else Path("outputs/enhanced")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*80}")
    print("  ENHANCED ACTIVITY INTELLIGENCE PIPELINE")
    print(f"{'═'*80}")

    # ── 1. Load AIS ───────────────────────────────────────────────────────────
    print(f"\n[1/6] Loading {Path(ais_path).name} …")
    df = load_ais_file(ais_path, source=source, max_rows=max_rows, bbox=bbox)
    if df.empty:
        print("  No data loaded.")
        return {}

    # Subsample vessels
    mmsis = df["mmsi"].unique()
    if len(mmsis) > max_vessels:
        rng   = np.random.default_rng(42)
        mmsis = rng.choice(mmsis, max_vessels, replace=False)
        df    = df[df["mmsi"].isin(mmsis)]
    counts = df["mmsi"].value_counts()
    df = df[df["mmsi"].isin(counts[counts >= 5].index)]
    print(f"      {df['mmsi'].nunique()} vessels  |  {len(df):,} pings")

    # ── 2. Compute segment features ───────────────────────────────────────────
    print("[2/6] Computing segment features …")
    seg_df = compute_segment_features(df, window_size=20, step_size=10, n_jobs=-1)
    print(f"      {len(seg_df):,} segments  |  {seg_df['mmsi'].nunique()} vessels")

    # ── 3. Geo-feature augmentation ───────────────────────────────────────────
    print("[3/6] Augmenting with GFW fishing effort + lane proximity …")
    aug      = GeoFeatureAugmenter(fetch_depth=False)

    # Add centroid lat/lon to seg_df if not present (derived from raw pings)
    if "centroid_lat" not in seg_df.columns and "lat" in df.columns:
        centroids = (
            df.groupby("mmsi")[["lat", "lon"]]
            .mean()
            .rename(columns={"lat": "centroid_lat", "lon": "centroid_lon"})
            .reset_index()
        )
        seg_df = seg_df.merge(centroids, on="mmsi", how="left")

    seg_df = aug.augment(seg_df,
                         lat_col="centroid_lat" if "centroid_lat" in seg_df.columns else "lat",
                         lon_col="centroid_lon" if "centroid_lon" in seg_df.columns else "lon")

    effort_mean = seg_df["gfw_effort"].mean() if "gfw_effort" in seg_df.columns else 0
    lane_mean   = seg_df["lane_proximity"].mean() if "lane_proximity" in seg_df.columns else 0
    print(f"      Mean GFW effort: {effort_mean:.3f}  |  Mean lane proximity: {lane_mean:.3f}")

    # ── 4. Train classifier + vessel baseline ─────────────────────────────────
    print("[4/6] Training classifier + per-vessel behavioural baselines …")
    from backend.dark_vessels.src.classifiers.classifier import ActivityIntelligenceClassifier

    # Add missing required columns if absent
    for col, val in [("true_activity", "transit"), ("vessel_type_key", "unknown"),
                     ("name", "unknown"), ("flag", "XX"),
                     ("length", 0), ("draught", 0)]:
        if col not in seg_df.columns:
            seg_df[col] = val

    # Use vessel_type from raw AIS if available
    if "vessel_type" in df.columns:
        vt_map = df.groupby("mmsi")["vessel_type"].agg(
            lambda x: x.mode().iloc[0] if len(x) > 0 else "unknown"
        )
        seg_df["vessel_type_key"] = seg_df["mmsi"].map(vt_map).fillna("unknown")

    # Derive pseudo true_activity from nav_status if present
    if "nav_status" in df.columns:
        from backend.dark_vessels.src.real_data_helpers.real_ais_loader import NAV_STATUS_ACTIVITY
        ns_mode = (
            df.groupby("mmsi")["nav_status"]
            .agg(lambda x: pd.to_numeric(x, errors="coerce").dropna().astype(int).mode().iloc[0]
                 if len(pd.to_numeric(x, errors="coerce").dropna()) > 0 else -1)
        )
        def _ns_to_act(ns):
            a = NAV_STATUS_ACTIVITY.get(int(ns), "transit")
            return a if a != "unknown" else "transit"
        seg_df["true_activity"] = seg_df["mmsi"].map(
            lambda m: _ns_to_act(ns_mode.get(m, -1))
        )

    # Train/test split
    all_mmsis = np.array(seg_df["mmsi"].unique())
    rng = np.random.default_rng(99)
    rng.shuffle(all_mmsis)
    split       = int(len(all_mmsis) * 0.7)
    train_mmsis = set(all_mmsis[:split])
    test_mmsis  = set(all_mmsis[split:])

    train_seg = seg_df[seg_df["mmsi"].isin(train_mmsis)]
    test_seg  = seg_df[seg_df["mmsi"].isin(test_mmsis)]

    clf = ActivityIntelligenceClassifier()
    clf.fit(train_seg)

    # Vessel baseline
    vbp = VesselBaselineProfiler(min_windows=5)
    vbp.fit(train_seg)
    seg_df = vbp.score(seg_df)

    print(f"      Baseline profiles: {len(vbp._profiles)} vessels")

    # Predict on all segments
    try:
        preds = clf.predict(seg_df)
        preds["mmsi"] = seg_df["mmsi"].values

        # Merge baseline anomaly score
        if "baseline_anomaly_score" in seg_df.columns:
            preds["baseline_anomaly_score"] = seg_df["baseline_anomaly_score"].values

        # Roll up to vessel level
        agg_cols = {
            "pred_activity":         ("pred_activity", lambda x: x.mode().iloc[0]),
            "pred_vessel_type":      ("pred_vessel_type", lambda x: x.mode().iloc[0]),
            "activity_confidence":   ("activity_confidence", "mean"),
            "dark_vessel_risk":      ("dark_vessel_risk", "max"),
            "iuu_fishing_risk":      ("iuu_fishing_risk", "max"),
            "sts_evasion_risk":      ("sts_evasion_risk", "max"),
            "overall_anomaly_score": ("overall_anomaly_score", "max"),
        }
        if "baseline_anomaly_score" in preds.columns:
            agg_cols["baseline_anomaly_score"] = ("baseline_anomaly_score", "max")

        vessel_results = (
            preds.groupby("mmsi")
            .agg(**agg_cols)
            .reset_index()
        )
    except Exception as e:
        print(f"  [classifier error: {e}]")
        vessel_results = pd.DataFrame({"mmsi": seg_df["mmsi"].unique()})

    # ── 5. Rendezvous detection ───────────────────────────────────────────────
    print("[5/6] Running rendezvous / proximity event detection …")
    rz     = RendezvousDetector(prox_nm=0.5, min_duration_s=600)
    events = rz.detect(df)

    if not events.empty:
        vessel_rz_risk = rz.vessel_risk_scores(events)
        vessel_results["rendezvous_risk"] = vessel_results["mmsi"].map(vessel_rz_risk).fillna(0)
        print(f"      {len(events)} rendezvous events  |  "
              f"max risk: {events['risk_score'].max():.2f}")
        if not vessel_results.empty and "overall_anomaly_score" in vessel_results.columns:
            _print_table(
                vessel_results.sort_values("overall_anomaly_score", ascending=False),
                cols=[c for c in ["mmsi", "pred_activity", "pred_vessel_type",
                                "activity_confidence", "iuu_fishing_risk",
                                "sts_evasion_risk", "rendezvous_risk",
                                "overall_anomaly_score"]
                    if c in vessel_results.columns],
                title="TOP VESSELS BY ANOMALY SCORE (Enhanced Intelligence)",
                n=20,
            )
            events.to_csv(out_dir / "rendezvous_events.csv", index=False)
        else:
            vessel_results["rendezvous_risk"] = 0.0
            print("      No rendezvous events detected")

    # Update composite anomaly score
    if "rendezvous_risk" in vessel_results.columns and "overall_anomaly_score" in vessel_results.columns:
        vessel_results["overall_anomaly_score"] = vessel_results[[
            "overall_anomaly_score", "rendezvous_risk"
        ]].max(axis=1)

    # ── 6. Dark-period dead-reckoning for top-risk vessels ────────────────────
    print("[6/6] Dark-period dead-reckoning for high-risk vessels …")
    dpp = DarkPeriodPredictor(n_samples=1000)
    dpp.fit(df)

    dark_periods = DarkPeriodPredictor.extract_dark_periods(df, gap_threshold_min=30.0)
    dark_summaries = []

    if not dark_periods.empty and not vessel_results.empty:
        top_risk_mmsis = set(
            vessel_results.nlargest(
                min(10, len(vessel_results)), "overall_anomaly_score"
            )["mmsi"].values
        )
        top_dark = dark_periods[dark_periods["mmsi"].isin(top_risk_mmsis)]
        for _, row in top_dark.iterrows():
            state = VesselState(
                mmsi        = int(row["mmsi"]),
                timestamp   = row["dark_start"],
                lat         = float(row["last_lat"]) if pd.notna(row["last_lat"]) else 0.0,
                lon         = float(row["last_lon"]) if pd.notna(row["last_lon"]) else 0.0,
                sog_kn      = float(row["last_sog"]) if pd.notna(row["last_sog"]) else 5.0,
                cog_deg     = float(row["last_cog"]) if pd.notna(row["last_cog"]) else 0.0,
                vessel_type = str(row["vessel_type"]),
            )
            try:
                summary = dpp.summarise(state, dt_hours=float(row["gap_hours"]))
                dark_summaries.append(summary)
            except Exception:
                pass

        if dark_summaries:
            dark_sum_df = pd.DataFrame(dark_summaries)
            dark_sum_df.to_csv(out_dir / "dark_period_cones.csv", index=False)
            print(f"      {len(dark_periods)} dark periods  |  "
                  f"{len(dark_summaries)} cones computed for top-risk vessels")
        else:
            print(f"      {len(dark_periods)} dark periods detected")
    else:
        print("      No dark periods detected")

    # ── Save & report ─────────────────────────────────────────────────────────
    vessel_results.to_csv(out_dir / "vessel_intelligence.csv", index=False)
    seg_df.to_csv(out_dir / "segments_augmented.csv", index=False)

    print(f"\n{'─'*80}")
    print("  ENHANCED INTELLIGENCE SUMMARY")
    print(f"{'─'*80}")
    print(f"  Vessels analysed:      {len(vessel_results)}")
    print(f"  Segments processed:    {len(seg_df):,}")
    if "overall_anomaly_score" in vessel_results.columns:
        high_risk = vessel_results[vessel_results["overall_anomaly_score"] > 0.5]
        print(f"  High-risk vessels:     {len(high_risk)}")
    print(f"  Rendezvous events:     {len(events) if not events.empty else 0}")
    print(f"  Dark periods logged:   {len(dark_periods)}")
    print(f"  Output dir:            {out_dir}/")

    if not vessel_results.empty and "overall_anomaly_score" in vessel_results.columns and visualise:
        _print_table(
            vessel_results.sort_values("overall_anomaly_score", ascending=False),
            cols=[c for c in ["mmsi", "pred_activity", "pred_vessel_type",
                               "activity_confidence", "iuu_fishing_risk",
                               "sts_evasion_risk", "rendezvous_risk",
                               "overall_anomaly_score"]
                  if c in vessel_results.columns],
            title="TOP VESSELS BY ANOMALY SCORE (Enhanced Intelligence)",
            n=20,
        )

    return {
        "n_vessels":     len(vessel_results),
        "n_segments":    len(seg_df),
        "n_rendezvous":  len(events) if not events.empty else 0,
        "n_dark_periods": len(dark_periods),
        "output_dir":    str(out_dir),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(visualise=False):
    parser = argparse.ArgumentParser(
        description="Maritime Activity Intelligence Engine")
    parser.add_argument("--region",  type=str, default=None,
                        help="Region key (e.g. brazil_eez, philippines_eez)")
    parser.add_argument("--all",     action="store_true",
                        help="Run all regions and compare")
    parser.add_argument("--list-regions", action="store_true")

    # Real AIS validation mode
    parser.add_argument("--real-ais", type=str, default=None,
                        help="Path to real AIS file (.csv or .zip) to validate classifier")
    parser.add_argument("--ais-source", type=str, default="auto",
                        choices=["auto", "noaa", "infore", "dma", "generic"],
                        help="AIS data source format (default: auto-detect)")
    parser.add_argument("--max-rows", type=int, default=2_000_000,
                        help="Max rows to load from AIS file (default: 2M)")
    parser.add_argument("--max-vessels", type=int, default=1000,
                        help="Max vessels to process (default: 1000)")
    parser.add_argument("--bbox", type=str, default=None,
                        help="Spatial filter: lon_min,lat_min,lon_max,lat_max")

    # Partial track training mode
    parser.add_argument("--partial-track", action="store_true",
                        help="Train & evaluate partial-track classifier on all downloaded AIS files")
    parser.add_argument("--ais-dir", type=str,
                        default="data/real_tracks",
                        help="Directory containing AIS zip files for partial-track training")

    # Enhanced intelligence mode (all new modules)
    parser.add_argument("--enhanced", action="store_true",
                        help="Run full enhanced intelligence pipeline (geo + rendezvous + baseline + dark predictor)")

    args = parser.parse_args()

    if args.list_regions:
        print("\nAvailable regions:")
        for k, v in REGIONS.items():
            print(f"  {k:<30} {v['name']}")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Enhanced intelligence mode ───────────────────────────────────────────
    if args.enhanced:
        if not args.real_ais:
            print("--enhanced requires --real-ais <path>")
            sys.exit(1)
        bbox = None
        if args.bbox:
            try:
                bbox = tuple(float(x) for x in args.bbox.split(","))
            except ValueError:
                print("--bbox must be: lon_min,lat_min,lon_max,lat_max")
                sys.exit(1)
        run_enhanced_intelligence(
            ais_path    = args.real_ais,
            source      = args.ais_source,
            max_rows    = args.max_rows,
            max_vessels = args.max_vessels,
            bbox        = bbox,
            output_dir  = OUTPUT_DIR / "enhanced",
        )
        return

    # ── Partial track training mode ──────────────────────────────────────────
    if args.partial_track:
        ais_dir = Path(args.ais_dir)
        ais_files = sorted(ais_dir.glob("*.zip"))
        # Exclude the small INFORE dataset (no nav_status GT, different schema)
        ais_files = [f for f in ais_files if "INFORE" not in f.name]
        if not ais_files:
            print(f"No AIS zip files found in {ais_dir}")
            sys.exit(1)
        print(f"  Found {len(ais_files)} AIS files: {[f.name for f in ais_files]}")
        run_partial_track_training(
            ais_files=[str(f) for f in ais_files],
            source="noaa",
            max_rows_per_file=1_500_000,
            max_vessels_per_file=2000,
            output_dir=str(OUTPUT_DIR / "partial_track"),
            model_save_path=str(OUTPUT_DIR / "partial_track" / "model.pkl"),
        )
        return

    # ── Real AIS validation mode ─────────────────────────────────────────────
    if args.real_ais:
        bbox = None
        if args.bbox:
            try:
                bbox = tuple(float(x) for x in args.bbox.split(","))
            except ValueError:
                print("--bbox must be: lon_min,lat_min,lon_max,lat_max")
                sys.exit(1)

        validate_real_ais(
            ais_path    = args.real_ais,
            source      = args.ais_source,
            max_rows    = args.max_rows,
            max_vessels = args.max_vessels,
            bbox        = bbox,
            output_dir  = OUTPUT_DIR / "real_ais",
        )
        return

    # ── Synthetic simulation mode ─────────────────────────────────────────────
    if args.all or args.region is None:
        compare_regions(list(REGIONS.keys()))
    else:
        if args.region not in REGIONS:
            print(f"Unknown region '{args.region}'. "
                  f"Use --list-regions to see options.")
            sys.exit(1)
        run_region(args.region, visualise=visualise)


if __name__ == "__main__":

    start_time = datetime.now()

    # data simulation for model training
    data = simulate_region('philippines_eez')
    print(data)
    sq = SequenceClassifier()
    sq.fit(data, epochs=200)
    print(sq.predict(data))
    data = simulate_region('brazil_eez')
    sq.fit(data)
    print(sq.predict(data))
    data = simulate_region('strait_of_malacca')
    sq.fit(data)
    print(sq.predict(data))
    data = simulate_region('gulf_of_guinea')
    sq.fit(data)
    print(sq.predict(data))
    sq.save('sequence_classifier.pkl')

    print(Fore.GREEN)
    time = datetime.now() - start_time
    print("Time passed: " + str(time))
    print(Fore.RESET)

    # vessel_locations = get_vessel_position_history_helper(209641000)
    # vessel_locations_dataframe = sq.ais_to_dataframe(vessel_locations)
    # print(sq.predict(vessel_locations_dataframe))

    # vessel activity prediction
    frames = []
    mmsis = get_all_mmsis()

    for mmsi in mmsis:
        track = get_vessel_position_history_helper(mmsi)

        print(Fore.BLUE)
        print(track)
        print(Fore.RESET)

        if not track:
            continue

        df = pd.DataFrame(track)
        df.rename(columns={"basedatetime": "timestamp"}, inplace=True)

        required = {'timestamp', 'lat', 'lon', 'sog', 'cog'}
        if not required.issubset(df.columns):
            continue

        df["mmsi"] = mmsi
        frames.append(df)

    if not frames:
        raise ValueError("No valid AIS data after filtering")

    
    print(Fore.GREEN)
    time = datetime.now() - start_time
    print("Time passed: " + str(time))
    print(Fore.RESET)

    locations_dataframe = pd.concat(frames, ignore_index=True)
    sq.fit(locations_dataframe)
    predictions = sq.predict(locations_dataframe)
    predictions.to_sql("dark_vessel_predictions", engine, if_exists="replace", index=False)

    # dark vessel analysis
    detector = DarkVesselDetector()
    dark_df  = detector.analyze_fleet(locations_dataframe)
    # print(Fore.GREEN)
    # time = datetime.now() - start_time
    # print("Time passed: " + str(time))
    # print(Fore.RESET)
    # spoofed_mmsis = detector.detect_mmsi_clones(locations_dataframe)

    n_dark_flagged = int((dark_df["dark_risk_score"] > 0.3).sum())
    print(f"      Vessels with dark risk > 0.3: {n_dark_flagged}")
    # print(f"      Suspected MMSI clones:         {len(spoofed_mmsis)}")

    dark_df.to_sql("dark_detections", engine, if_exists="replace", index=False)

    print(Fore.GREEN)
    time = datetime.now() - start_time
    print("Final time passed: " + str(time))
    print(Fore.RESET)