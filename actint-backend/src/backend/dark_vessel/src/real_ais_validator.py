"""
Real AIS Classifier Validator

Runs the Activity Intelligence pipeline on real AIS track data and produces:
  1. Per-vessel activity predictions
  2. Confusion matrix (where nav_status ground truth is available)
  3. Type distribution comparison (predicted vs. reported ITU types)
  4. Interactive Folium map of real tracks with classifier predictions
  5. Console performance report

Usage from Python:
    from src.real_ais_validator import validate_real_ais
    results = validate_real_ais("data/real_tracks/AIS_2023_06_01.zip",
                                 source="noaa", max_vessels=500)
"""

import numpy as np
import pandas as pd
import folium
from folium.plugins import HeatMap
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

from .real_ais_loader import (
    load_ais_file, fleet_summary, type_distribution,
    NAV_STATUS_ACTIVITY, VESSEL_TYPE_LABELS,
)
from .features import compute_segment_features
from .classifier import ActivityIntelligenceClassifier

# ── Activity colours (consistent with existing visualiser) ──────────────────
ACTIVITY_COLORS = {
    "fishing":  "#00ff88",
    "transit":  "#4488ff",
    "anchored": "#ffaa00",
    "loiter":   "#ff44ff",
    "sts":      "#ff2222",
    "port":     "#ffffff",
    "unknown":  "#888888",
}

VESSEL_TYPE_COLORS = {
    "fishing":        "#00ff88",
    "cargo":          "#4488ff",
    "tanker":         "#ff8800",
    "passenger":      "#cc44ff",
    "naval":          "#ff2222",
    "tug":            "#ffff00",
    "support_vessel": "#00ccff",
    "hsc":            "#ff99cc",
    "sailing":        "#aaffaa",
    "pleasure_craft": "#ffccaa",
    "other":          "#888888",
    "unknown":        "#444444",
}


# ── Core validation function ──────────────────────────────────────────────────

def validate_real_ais(
    ais_path: str | Path,
    source:   str = "auto",
    max_rows: int | None = 2_000_000,
    max_vessels: int | None = 1000,
    bbox:     tuple | None = None,
    output_dir: str | Path = "outputs/real_ais",
    train_fraction: float = 0.7,
) -> dict:
    """
    Run the full classifier pipeline on a real AIS file.

    Returns dict with:
      predictions_df  — vessel-level roll-up
      eval_results    — confusion matrix, classification report, F1 scores
                        (only populated if nav_status ground truth exists)
      type_dist_df    — vessel type distribution
      output_dir      — where charts and map were saved
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*72}")
    print(f"  REAL AIS VALIDATOR — {Path(ais_path).name}")
    print(f"{'═'*72}")

    # ── 1. Load & filter ─────────────────────────────────────────────────────
    print(f"[1/5] Loading {Path(ais_path).name} ...")
    df = load_ais_file(ais_path, source=source, max_rows=max_rows, bbox=bbox)

    n_total  = len(df)
    n_vessels_all = df["mmsi"].nunique()
    print(f"      {n_total:,} pings  |  {n_vessels_all:,} vessels  "
          f"|  source={df['source'].iloc[0]}")

    # Subsample to max_vessels (deterministic)
    if max_vessels and n_vessels_all > max_vessels:
        rng = np.random.default_rng(42)
        keep = rng.choice(df["mmsi"].unique(), max_vessels, replace=False)
        df = df[df["mmsi"].isin(keep)].copy()
        print(f"      Subsampled to {max_vessels} vessels  ({len(df):,} pings)")

    # Drop vessels with fewer than 20 pings (min for one segment window)
    counts = df["mmsi"].value_counts()
    valid  = counts[counts >= 20].index
    df = df[df["mmsi"].isin(valid)].copy()
    n_vessels = df["mmsi"].nunique()
    print(f"      After ≥20 ping filter: {n_vessels} vessels  ({len(df):,} pings)")

    # ── 2. Type & activity distribution ──────────────────────────────────────
    print("[2/5] Computing type and activity distributions ...")
    type_dist = type_distribution(df)
    print("      Vessel types detected:")
    for _, row in type_dist.iterrows():
        bar = "█" * int(row["pct_pings"] * 40)
        print(f"        {row['label']:<25} {bar:<40} "
              f"{row['n_vessels']:>5} vessels  {row['pct_pings']:.1%}")

    # Ground truth available?
    has_gt = (df["true_activity"] != "unknown").sum() / len(df) > 0.3
    if has_gt:
        act_dist = df["true_activity"].value_counts(normalize=True)
        print(f"      Nav-status ground truth: {has_gt} ({act_dist.to_dict()})")

    # ── 3. Segment features ───────────────────────────────────────────────────
    print("[3/5] Computing segment features ...")
    # Bridge real AIS schema → feature pipeline schema
    df_pipe = df.copy()
    df_pipe["name"]           = df_pipe["vessel_name"].fillna("")
    df_pipe["flag"]           = df_pipe["mmsi"].str[:3]   # MID prefix as proxy flag
    df_pipe["vessel_type_key"]= df_pipe["vessel_type"]
    df_pipe["length"]         = df_pipe["length_m"].fillna(0).astype(int)
    df_pipe["draught"]        = 0.0

    # Derive pseudo-labels from nav_status and vessel_type when GT is absent
    # Real GT comes from nav_status; fallback uses vessel_type heuristic
    _vtype_to_activity = {
        "fishing": "fishing",
        "sailing": "transit",
        "passenger": "transit",
        "hsc": "transit",
        "cargo": "transit",
        "tanker": "transit",
        "tug": "transit",
        "support_vessel": "transit",
        "naval": "transit",
        "pleasure_craft": "transit",
        "other": "transit",
    }
    pseudo = df_pipe["vessel_type"].map(_vtype_to_activity).fillna("transit")
    # Override with nav_status where available (always preferred)
    nav_act = df_pipe["true_activity"].replace("unknown", pd.NA)
    df_pipe["true_activity"] = nav_act.fillna(pseudo)

    seg_df = compute_segment_features(df_pipe, region_key=None, window_size=20, step_size=10)
    print(f"      {len(seg_df):,} segments  |  {len(seg_df.columns)} features")

    # ── 4. Classifier — train on subset, predict on all ──────────────────────
    print("[4/5] Training and predicting ...")
    all_mmsis = np.array(seg_df["mmsi"].unique())
    rng = np.random.default_rng(42)
    rng.shuffle(all_mmsis)
    split = int(len(all_mmsis) * train_fraction)
    train_mmsis = set(all_mmsis[:split])
    test_mmsis  = set(all_mmsis[split:])

    train_seg = seg_df[seg_df["mmsi"].isin(train_mmsis)]
    test_seg  = seg_df[seg_df["mmsi"].isin(test_mmsis)]

    clf = ActivityIntelligenceClassifier()
    clf.fit(train_seg)

    eval_results = {}
    if has_gt and len(test_seg) > 50:
        # Only evaluate on segments where nav_status GT is known
        test_known = test_seg[test_seg["true_activity"] != "unknown"]
        if len(test_known) > 50:
            eval_results = clf.evaluate(test_known)
            report = eval_results.get("classification_report", {})
            macro_f1    = report.get("macro avg",    {}).get("f1-score", 0)
            weighted_f1 = report.get("weighted avg", {}).get("f1-score", 0)
            print(f"      Macro F1:    {macro_f1:.3f}  (on REAL nav-status labels)")
            print(f"      Weighted F1: {weighted_f1:.3f}")

    # Predict on all segments
    seg_preds = clf.predict(seg_df)
    seg_preds["mmsi"] = seg_df["mmsi"].values

    vessel_rollup = (
        seg_preds.groupby("mmsi")
        .agg(
            pred_activity        = ("pred_activity", lambda x: x.mode().iloc[0]),
            pred_vessel_type     = ("pred_vessel_type", lambda x: x.mode().iloc[0]),
            activity_confidence  = ("activity_confidence", "mean"),
            dark_vessel_risk     = ("dark_vessel_risk", "max"),
            iuu_fishing_risk     = ("iuu_fishing_risk", "max"),
            sts_evasion_risk     = ("sts_evasion_risk", "max"),
            overall_anomaly_score= ("overall_anomaly_score", "max"),
        )
        .reset_index()
    )

    # Merge real vessel metadata
    meta = fleet_summary(df)
    vessel_rollup = vessel_rollup.merge(
        meta[["mmsi", "vessel_name", "vessel_type", "n_pings",
              "sog_mean", "length_m", "imo"]],
        on="mmsi", how="left"
    )
    vessel_rollup["reported_type_label"] = (
        vessel_rollup["vessel_type"].map(VESSEL_TYPE_LABELS).fillna(vessel_rollup["vessel_type"])
    )

    high_risk = vessel_rollup[vessel_rollup["overall_anomaly_score"] > 0.5]
    print(f"      High-risk vessels (score > 0.5): {len(high_risk)}")

    # ── 5. Outputs ────────────────────────────────────────────────────────────
    print("[5/5] Generating outputs ...")

    # CSVs
    df.to_csv(out_dir / "real_tracks_normalised.csv", index=False)
    vessel_rollup.to_csv(out_dir / "vessel_predictions.csv", index=False)
    type_dist.to_csv(out_dir / "type_distribution.csv", index=False)

    # Charts
    _plot_type_distribution(type_dist, vessel_rollup,
                             str(out_dir / "type_distribution.png"),
                             source=df["source"].iloc[0])

    if eval_results:
        _plot_real_confusion(eval_results,
                              str(out_dir / "real_confusion_matrix.png"))

    _plot_sog_by_type(df, str(out_dir / "sog_by_vessel_type.png"))

    # Map
    map_path = _build_real_ais_map(df, vessel_rollup,
                                    str(out_dir / "real_ais_map.html"))
    print(f"      Map: {map_path}")

    # Console summary
    _print_summary(vessel_rollup, eval_results, Path(ais_path).name)

    return {
        "predictions_df":  vessel_rollup,
        "eval_results":    eval_results,
        "type_dist_df":    type_dist,
        "n_pings":         len(df),
        "n_vessels":       n_vessels,
        "output_dir":      str(out_dir),
        "map_path":        map_path,
    }


# ── Visualisations ────────────────────────────────────────────────────────────

def _plot_type_distribution(type_dist: pd.DataFrame,
                             vessel_rollup: pd.DataFrame,
                             output_path: str,
                             source: str = "") -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor("#0d0d1a")
    fig.suptitle(f"Vessel Type Distribution — Real AIS Data ({source})",
                 color="white", fontsize=13, fontweight="bold")

    for ax in axes:
        ax.set_facecolor("#12122a")
        ax.tick_params(colors="white", labelsize=9)
        for sp in ax.spines.values():
            sp.set_edgecolor("#333")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    # Left: reported ITU type by vessel count
    ax = axes[0]
    top = type_dist.head(10)
    colors = [VESSEL_TYPE_COLORS.get(t, "#888") for t in top["vessel_type"]]
    ax.barh(top["label"], top["n_vessels"], color=colors, edgecolor="#111")
    ax.set_title("Reported Vessel Types (ITU codes)\nby unique vessel count")
    ax.set_xlabel("Vessels")

    # Right: classifier predicted activity distribution
    ax = axes[1]
    pred_dist = vessel_rollup["pred_activity"].value_counts()
    act_labels = {
        "fishing": "Fishing", "transit": "Transit", "anchored": "Anchored/Moored",
        "loiter": "Loitering", "sts": "STS Transfer", "port": "In Port",
    }
    act_colors = [ACTIVITY_COLORS.get(a, "#888") for a in pred_dist.index]
    ax.barh([act_labels.get(a, a) for a in pred_dist.index],
            pred_dist.values, color=act_colors, edgecolor="#111")
    ax.set_title("Classifier Predicted Activities\n(real AIS tracks)")
    ax.set_xlabel("Vessels")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()


def _plot_real_confusion(eval_results: dict, output_path: str) -> None:
    from .visualizer import plot_confusion_matrix
    plot_confusion_matrix(
        eval_results["confusion_matrix"],
        eval_results["labels"],
        "real_ais",
        output_path,
    )


def _plot_sog_by_type(df: pd.DataFrame, output_path: str) -> None:
    """SOG distribution per vessel type."""
    types = [t for t in VESSEL_TYPE_COLORS if t in df["vessel_type"].unique()]
    if not types:
        return

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#0d0d1a")
    ax.set_facecolor("#12122a")
    ax.tick_params(colors="white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#333")
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")

    from scipy.stats import gaussian_kde
    x = np.linspace(0, 35, 300)
    for vtype in types:
        sub = df[(df["vessel_type"] == vtype) & (df["sog"] > 0) & (df["sog"] < 40)]
        if len(sub) < 50:
            continue
        try:
            kde = gaussian_kde(sub["sog"].values, bw_method=0.15)
            label = VESSEL_TYPE_LABELS.get(vtype, vtype)
            ax.plot(x, kde(x), label=label, color=VESSEL_TYPE_COLORS.get(vtype, "#888"),
                    linewidth=1.8, alpha=0.85)
        except Exception:
            pass

    ax.set_xlabel("Speed Over Ground (knots)")
    ax.set_ylabel("Density")
    ax.set_title("Speed Profile by Vessel Type — Real AIS Data")
    leg = ax.legend(fontsize=8, facecolor="#1a1a2e", labelcolor="white", framealpha=0.8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()


def _build_real_ais_map(df: pd.DataFrame,
                         vessel_rollup: pd.DataFrame,
                         output_path: str) -> str:
    """Interactive Folium map: real vessel tracks coloured by classifier prediction."""
    center_lat = float(df["lat"].median())
    center_lon = float(df["lon"].median())

    m = folium.Map(location=[center_lat, center_lon], zoom_start=6,
                   tiles="CartoDB dark_matter")

    title_html = f"""
    <div style="position:fixed; top:10px; left:50%; transform:translateX(-50%);
         z-index:9999; background:rgba(0,0,0,0.75); color:white;
         padding:8px 18px; border-radius:6px; font-family:sans-serif; font-size:14px">
      Activity Intelligence — Real AIS Tracks ({df['source'].iloc[0].upper()})
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # Merge rollup predictions back into ping-level data for colouring
    pred_map = vessel_rollup.set_index("mmsi")["pred_activity"].to_dict()
    risk_map  = vessel_rollup.set_index("mmsi")["overall_anomaly_score"].to_dict()

    # Heatmap of all pings
    heat_data = [[float(r["lat"]), float(r["lon"])]
                 for _, r in df.sample(min(len(df), 50000), random_state=42).iterrows()]
    HeatMap(heat_data, radius=8, blur=12, min_opacity=0.2,
            name="Ping Density Heatmap").add_to(m)

    # Tracks per vessel (sample up to 300 vessels to keep map performant)
    track_group = folium.FeatureGroup(name="Vessel Tracks", show=True)
    top_mmsis = vessel_rollup.nlargest(300, "n_pings")["mmsi"].tolist()

    for mmsi in top_mmsis:
        sub = df[df["mmsi"] == mmsi].sort_values("timestamp")
        if len(sub) < 5:
            continue
        coords = list(zip(sub["lat"].values, sub["lon"].values))
        pred_act  = pred_map.get(mmsi, "unknown")
        risk      = risk_map.get(mmsi, 0)
        color     = ACTIVITY_COLORS.get(pred_act, "#888888")
        weight    = 1 + int(risk * 3)

        row = vessel_rollup[vessel_rollup["mmsi"] == mmsi]
        vname  = row["vessel_name"].iloc[0] if len(row) else mmsi
        vtype  = row["reported_type_label"].iloc[0] if len(row) else ""
        vtypep = row.get("pred_vessel_type", pd.Series([""])).iloc[0] if len(row) else ""

        folium.PolyLine(
            coords, color=color, weight=weight, opacity=0.7,
            tooltip=f"{vname} | {vtype} → pred:{pred_act} | risk:{risk:.2f}",
        ).add_to(track_group)

    track_group.add_to(m)

    # High-risk markers
    flagged_group = folium.FeatureGroup(name="High-Risk Vessels (score > 0.5)", show=True)
    for _, row in vessel_rollup[vessel_rollup["overall_anomaly_score"] > 0.5].iterrows():
        sub = df[df["mmsi"] == row["mmsi"]]
        if sub.empty:
            continue
        last = sub.sort_values("timestamp").iloc[-1]
        folium.CircleMarker(
            location=[float(last["lat"]), float(last["lon"])],
            radius=6 + row["overall_anomaly_score"] * 10,
            color="#ff2222", fill=True, fill_color="#ff2222", fill_opacity=0.8,
            tooltip=f"{row['vessel_name']} | {row['reported_type_label']} "
                    f"| pred:{row['pred_activity']} | risk:{row['overall_anomaly_score']:.2f}",
        ).add_to(flagged_group)
    flagged_group.add_to(m)

    # Legend
    legend_items = "".join(
        f'<div><span style="background:{c};display:inline-block;'
        f'width:14px;height:14px;margin-right:6px"></span>{a}</div>'
        for a, c in ACTIVITY_COLORS.items() if a != "unknown"
    )
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed; bottom:20px; right:10px; z-index:9999;
         background:rgba(0,0,0,0.75); color:white; padding:10px;
         border-radius:6px; font-family:monospace; font-size:11px">
      <b>Predicted Activity</b><br>{legend_items}
    </div>
    """))

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(output_path)
    return output_path


# ── Console summary ───────────────────────────────────────────────────────────

def _print_summary(vessel_rollup: pd.DataFrame,
                    eval_results: dict,
                    filename: str) -> None:
    print(f"\n{'═'*72}")
    print(f"  REAL AIS INTELLIGENCE SUMMARY — {filename}")
    print(f"{'═'*72}")

    print(f"\n  Predicted activity distribution:")
    act_dist = vessel_rollup["pred_activity"].value_counts()
    for act, cnt in act_dist.items():
        bar = "█" * int(cnt / act_dist.max() * 35)
        print(f"    {act:<14}  {bar:<35}  {cnt:>5}")

    print(f"\n  Reported vessel type (ITU) distribution:")
    vt_dist = vessel_rollup["reported_type_label"].value_counts()
    for vt, cnt in vt_dist.head(10).items():
        bar = "█" * int(cnt / vt_dist.max() * 35)
        print(f"    {vt:<28}  {bar:<35}  {cnt:>5}")

    high_risk = vessel_rollup[vessel_rollup["overall_anomaly_score"] > 0.5]
    print(f"\n  High-risk vessels (score > 0.5): {len(high_risk)}")
    if not high_risk.empty:
        cols = ["mmsi", "vessel_name", "reported_type_label",
                "pred_activity", "overall_anomaly_score", "iuu_fishing_risk"]
        print(high_risk[cols].head(10).to_string(index=False))

    if eval_results:
        report = eval_results.get("classification_report", {})
        macro_f1    = report.get("macro avg",    {}).get("f1-score", 0)
        weighted_f1 = report.get("weighted avg", {}).get("f1-score", 0)
        print(f"\n  Classifier vs. nav-status ground truth:")
        print(f"    Macro F1:    {macro_f1:.3f}")
        print(f"    Weighted F1: {weighted_f1:.3f}")
        for label in eval_results.get("labels", []):
            r = report.get(label, {})
            if isinstance(r, dict):
                print(f"    {label:<12}  P={r.get('precision',0):.2f}  "
                      f"R={r.get('recall',0):.2f}  F1={r.get('f1-score',0):.2f}  "
                      f"n={r.get('support',0)}")
    print()
