"""
Visualization module: Folium interactive maps + Matplotlib/Seaborn analytics charts.
"""

import numpy as np
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from pathlib import Path


ACTIVITY_COLORS = {
    "fishing":  "#1f77b4",
    "transit":  "#2ca02c",
    "anchored": "#ff7f0e",
    "loiter":   "#d62728",
    "sts":      "#9467bd",
    "port":     "#8c564b",
    "unknown":  "#7f7f7f",
}

RISK_COLORMAP = ["#00cc44", "#ffff00", "#ff8800", "#ff0000"]

VESSEL_ICONS = {
    "trawler":       "fish",
    "longliner":     "fish",
    "purse_seiner":  "fish",
    "cargo":         "ship",
    "tanker":        "tint",
    "bulk_carrier":  "ship",
    "naval":         "shield",
    "support_vessel":"wrench",
}


def _risk_color(score: float) -> str:
    score = max(0.0, min(1.0, float(score)))
    r = int(score * 255)
    g = int((1 - score) * 200)
    return f"#{r:02x}{g:02x}00"


def _activity_color(activity: str) -> str:
    return ACTIVITY_COLORS.get(activity, ACTIVITY_COLORS["unknown"])


# ---------------------------------------------------------------------------
# Interactive map
# ---------------------------------------------------------------------------

def build_region_map(
    raw_df: pd.DataFrame,
    results_df: pd.DataFrame,
    dark_df: pd.DataFrame,
    region_key: str,
    output_path: str,
) -> str:
    """
    Build an interactive folium map showing:
      - Vessel tracks coloured by predicted activity
      - Markers for high-risk / dark vessels
      - Heatmap of vessel density
      - Region info layers
    """
    from .regions import REGIONS

    region = REGIONS[region_key]
    bbox   = region["bbox"]
    center_lat = (bbox[1] + bbox[3]) / 2
    center_lon = (bbox[0] + bbox[2]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles="CartoDB dark_matter",
    )

    # ---- Track layer (coloured by true_activity) ----
    track_layer = folium.FeatureGroup(name="Vessel Tracks", show=True)
    for mmsi, grp in raw_df.groupby("mmsi"):
        grp = grp.sort_values("timestamp")
        coords = list(zip(grp["lat"], grp["lon"]))
        if len(coords) < 2:
            continue

        activity = grp["true_activity"].mode().iloc[0] if "true_activity" in grp.columns else "unknown"
        color = _activity_color(activity)

        # Only visible (AIS-on) segments
        ais_on = grp["ais_on"].values if "ais_on" in grp.columns else np.ones(len(grp), bool)
        seg_coords = []
        for i, (lat, lon) in enumerate(coords):
            if ais_on[i]:
                seg_coords.append((lat, lon))
            else:
                if len(seg_coords) > 1:
                    folium.PolyLine(
                        seg_coords, color=color,
                        weight=1.5, opacity=0.7,
                        tooltip=f"MMSI {mmsi} | {activity}"
                    ).add_to(track_layer)
                seg_coords = []
        if len(seg_coords) > 1:
            folium.PolyLine(
                seg_coords, color=color,
                weight=1.5, opacity=0.7,
                tooltip=f"MMSI {mmsi} | {activity}"
            ).add_to(track_layer)

    track_layer.add_to(m)

    # ---- Dark segments (dashed red) ----
    dark_layer = folium.FeatureGroup(name="Dark/AIS-Off Segments", show=True)
    for mmsi, grp in raw_df.groupby("mmsi"):
        grp = grp.sort_values("timestamp")
        ais_on = grp["ais_on"].values if "ais_on" in grp.columns else np.ones(len(grp), bool)
        coords = list(zip(grp["lat"], grp["lon"]))
        dark_seg = []
        for i in range(len(coords)):
            if not ais_on[i]:
                dark_seg.append(coords[i])
            else:
                if len(dark_seg) > 1:
                    folium.PolyLine(
                        dark_seg, color="#ff0000",
                        weight=2, opacity=0.9,
                        dash_array="8 4",
                        tooltip=f"MMSI {mmsi} — DARK PERIOD"
                    ).add_to(dark_layer)
                dark_seg = []
        if len(dark_seg) > 1:
            folium.PolyLine(
                dark_seg, color="#ff0000", weight=2,
                dash_array="8 4", opacity=0.9,
                tooltip=f"MMSI {mmsi} — DARK PERIOD"
            ).add_to(dark_layer)
    dark_layer.add_to(m)

    # ---- Vessel markers with risk colour ----
    marker_layer = folium.FeatureGroup(name="Vessel Markers", show=True)
    merged = results_df.merge(
        dark_df[["mmsi", "dark_risk_score", "anomaly_flags"]],
        on="mmsi", how="left"
    )
    vessel_positions = raw_df.groupby("mmsi")[["lat", "lon"]].last().reset_index()
    merged = merged.merge(vessel_positions, on="mmsi", how="left")

    for _, row in merged.iterrows():
        risk  = row.get("dark_risk_score", 0) or 0
        color = _risk_color(risk)
        activity = row.get("pred_activity", "unknown")
        vtype    = row.get("pred_vessel_type", "unknown")
        conf_a   = row.get("activity_confidence", 0)
        conf_v   = row.get("vessel_confidence", 0)
        flags    = row.get("anomaly_flags", "NONE")
        name     = row.get("name", str(row["mmsi"]))
        flag_iso = row.get("flag", "??")

        popup_html = f"""
        <div style="font-family:monospace; min-width:260px">
          <b>{name}</b> &nbsp;<small>({flag_iso})</small><br>
          <hr style="margin:4px 0">
          <b>MMSI:</b> {row['mmsi']}<br>
          <b>Vessel type:</b> {row.get('pred_vessel_label', vtype)} ({conf_v:.0%})<br>
          <b>Activity:</b> {row.get('pred_activity_label', activity)} ({conf_a:.0%})<br>
          <hr style="margin:4px 0">
          <b>Dark risk:</b> {risk:.2f}<br>
          <b>IUU risk:</b> {row.get('iuu_fishing_risk',0):.2f}<br>
          <b>STS risk:</b> {row.get('sts_evasion_risk',0):.2f}<br>
          <b>Anomalies:</b> {flags}<br>
        </div>
        """
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=7 + risk * 8,
            color=color, fill=True, fill_color=color, fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{name} | {activity} | risk={risk:.2f}",
        ).add_to(marker_layer)
    marker_layer.add_to(m)

    # ---- Heatmap ----
    heat_layer = folium.FeatureGroup(name="Vessel Density Heatmap", show=False)
    heat_data  = raw_df[["lat", "lon"]].dropna().values.tolist()
    HeatMap(heat_data, radius=12, blur=15, min_opacity=0.3).add_to(heat_layer)
    heat_layer.add_to(m)

    # ---- Port markers ----
    port_layer = folium.FeatureGroup(name="Ports", show=True)
    for p in region.get("primary_ports", []):
        folium.Marker(
            [p["lat"], p["lon"]],
            icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
            tooltip=f"Port: {p['name']}",
        ).add_to(port_layer)
    port_layer.add_to(m)

    # ---- Fishing grounds ----
    if "fishing_grounds" in region:
        fg_layer = folium.FeatureGroup(name="Fishing Grounds", show=True)
        for g in region["fishing_grounds"]:
            r_deg = g.get("radius_nm", 100) / 60.0
            folium.Circle(
                [g["lat"], g["lon"]],
                radius=r_deg * 111_000,   # approx metres
                color="#1f77b4", fill=True,
                fill_opacity=0.08, weight=1.5,
                tooltip=f"Fishing ground: {g['name']}",
            ).add_to(fg_layer)
        fg_layer.add_to(m)

    # ---- Oil fields ----
    if "oil_fields" in region:
        oil_layer = folium.FeatureGroup(name="Oil Fields", show=True)
        for o in region["oil_fields"]:
            folium.Marker(
                [o["lat"], o["lon"]],
                icon=folium.Icon(color="orange", icon="tint", prefix="fa"),
                tooltip=f"Oil field: {o['name']}",
            ).add_to(oil_layer)
        oil_layer.add_to(m)

    # ---- Region EEZ boundary ----
    eez_layer = folium.FeatureGroup(name="EEZ Boundary", show=True)
    poly = region["polygon"]
    if poly.geom_type == "Polygon":
        coords = [(lat, lon) for lon, lat in poly.exterior.coords]
        folium.Polygon(
            coords, color="#ffffff", fill=False,
            weight=1.5, opacity=0.4,
            tooltip=region["name"],
        ).add_to(eez_layer)
    eez_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # ---- Title ----
    title_html = f"""
    <div style="position:fixed; top:10px; left:50%; transform:translateX(-50%);
         z-index:9999; background:rgba(0,0,0,0.75); color:white;
         padding:8px 18px; border-radius:6px; font-family:sans-serif; font-size:15px">
      Activity Intelligence — {region['name']}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    m.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Analytics charts
# ---------------------------------------------------------------------------

def plot_activity_distribution(results_df: pd.DataFrame, region_key: str,
                                 output_path: str):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor("#1a1a2e")
    for ax in axes:
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for sp in ax.spines.values():
            sp.set_edgecolor("#444")

    # Activity breakdown
    act_counts = results_df["pred_activity"].value_counts()
    colors = [_activity_color(a) for a in act_counts.index]
    axes[0].barh(act_counts.index, act_counts.values, color=colors)
    axes[0].set_title(f"Predicted Activities — {region_key}")
    axes[0].set_xlabel("Vessel count")

    # Risk score distribution
    axes[1].hist(results_df["overall_anomaly_score"], bins=20,
                 color="#ff4444", edgecolor="#333", alpha=0.85)
    axes[1].axvline(0.5, color="yellow", linestyle="--", alpha=0.7, label="Medium risk")
    axes[1].axvline(0.75, color="red", linestyle="--", alpha=0.7, label="High risk")
    axes[1].set_title("Overall Anomaly Score Distribution")
    axes[1].set_xlabel("Score")
    axes[1].legend(facecolor="#222", labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return output_path


def plot_confusion_matrix(cm: np.ndarray, labels: list,
                           region_key: str, output_path: str):
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    cm_norm = cm.astype(float) / (cm.sum(axis=1, keepdims=True) + 1e-9)
    sns.heatmap(
        cm_norm, annot=cm, fmt="d", cmap="Blues",
        xticklabels=labels, yticklabels=labels,
        ax=ax, linewidths=0.5
    )
    ax.set_title(f"Activity Classifier — {region_key}", color="white", pad=12)
    ax.set_ylabel("True", color="white")
    ax.set_xlabel("Predicted", color="white")
    ax.tick_params(colors="white")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return output_path


def plot_feature_importance(fi: pd.Series, region_key: str, output_path: str):
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    top = fi.head(15)
    colors = plt.cm.plasma(np.linspace(0.2, 0.9, len(top)))
    ax.barh(top.index[::-1], top.values[::-1], color=colors[::-1])
    ax.set_title(f"Top Feature Importances — {region_key}", color="white")
    ax.set_xlabel("Importance", color="white")
    ax.tick_params(colors="white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return output_path


def plot_speed_profiles(raw_df: pd.DataFrame, region_key: str, output_path: str):
    """Speed distribution per true activity type."""
    if "true_activity" not in raw_df.columns:
        return None

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")

    for act, color in ACTIVITY_COLORS.items():
        subset = raw_df[raw_df["true_activity"] == act]["sog"]
        if len(subset) > 10:
            sns.kdeplot(subset, ax=ax, label=act, color=color, fill=True, alpha=0.25)

    ax.set_title(f"Speed (SOG) Profile by Activity — {region_key}")
    ax.set_xlabel("Speed Over Ground (knots)")
    ax.legend(facecolor="#222", labelcolor="white")
    ax.set_xlim(0, 25)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return output_path
