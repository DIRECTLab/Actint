"""
Visualization and analysis using real GFW data.

Produces:
  1. Real fishing intensity heatmap (Folium)
  2. Fleet composition charts (flag state, gear type, monthly rhythm)
  3. Comparison: synthetic model predictions vs. real GFW fishing patterns
"""

import numpy as np
import pandas as pd
import folium
from folium.plugins import HeatMap
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from .real_data import (
    load_region_fleet, load_vessel_registry,
    region_fishing_stats, build_real_data_heatmap,
    GFW_GEARTYPE_MAP, MONTHS,
)
from ..util.regions import REGIONS


GEAR_COLORS = {
    "trawlers":            "#e41a1c",
    "fishing":             "#fb9a99",
    "drifting_longlines":  "#377eb8",
    "set_longlines":       "#a6cee3",
    "other_purse_seines":  "#4daf4a",
    "tuna_purse_seines":   "#b2df8a",
    "squid_jigger":        "#ff7f00",
    "set_gillnets":        "#fdbf6f",
    "fixed_gear":          "#984ea3",
    "trawler":             "#e41a1c",
    "longliner":           "#377eb8",
    "purse_seiner":        "#4daf4a",
    "other":               "#999999",
}


def build_real_fishing_map(region_key: str, output_path: str) -> str:
    """
    Interactive Folium map of REAL GFW fishing effort for a region.
    Heatmap layer = fishing intensity. Marker layer = dominant gear cells.
    """
    region  = REGIONS[region_key]
    bbox    = region["bbox"]
    center  = ((bbox[1]+bbox[3])/2, (bbox[0]+bbox[2])/2)

    df      = load_region_fleet(region_key)
    heatmap = build_real_data_heatmap(region_key)

    m = folium.Map(location=center, zoom_start=5,
                   tiles="CartoDB dark_matter")

    # Title
    title_html = f"""
    <div style="position:fixed; top:10px; left:50%; transform:translateX(-50%);
         z-index:9999; background:rgba(0,0,0,0.75); color:white;
         padding:8px 18px; border-radius:6px; font-family:sans-serif; font-size:15px">
      Real GFW Fishing Effort 2023 — {region['name']}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── Fishing hours heatmap ──
    heat_data = []
    for _, row in heatmap.iterrows():
        w = float(row["intensity_norm"])
        if w > 0.001:
            heat_data.append([float(row["cell_lat"]), float(row["cell_lon"]), w])
    if heat_data:
        HeatMap(heat_data, radius=14, blur=18, min_opacity=0.2,
                max_val=1.0, name="Fishing Intensity Heatmap",
                show=True).add_to(m)

    # ── Top fishing cells ──
    top_cells = folium.FeatureGroup(name="Top Fishing Hotspots", show=True)
    for _, row in heatmap.head(50).iterrows():
        gear  = row["dominant_gear"]
        flag  = row["dominant_flag"]
        fh    = row["total_fishing_hours"]
        color = GEAR_COLORS.get(gear, "#ffffff")
        folium.CircleMarker(
            location=[row["cell_lat"], row["cell_lon"]],
            radius=4 + row["intensity_norm"] * 12,
            color=color, fill=True, fill_color=color, fill_opacity=0.75,
            tooltip=f"{gear} | {flag} | {fh:.0f} fishing-hrs",
            popup=folium.Popup(
                f"<b>Gear:</b> {gear}<br><b>Flag:</b> {flag}<br>"
                f"<b>Fishing hours:</b> {fh:.1f}<br>"
                f"<b>Cell:</b> {row['cell_lat']:.1f}°, {row['cell_lon']:.1f}°",
                max_width=250)
        ).add_to(top_cells)
    top_cells.add_to(m)

    # ── Ports ──
    if "primary_ports" in region:
        pl = folium.FeatureGroup(name="Ports", show=True)
        for p in region["primary_ports"]:
            folium.Marker([p["lat"], p["lon"]],
                          icon=folium.Icon(color="blue", icon="anchor", prefix="fa"),
                          tooltip=f"Port: {p['name']}").add_to(pl)
        pl.add_to(m)

    # ── EEZ boundary ──
    poly = region["polygon"]
    if poly.geom_type == "Polygon":
        coords = [(lat, lon) for lon, lat in poly.exterior.coords]
        folium.Polygon(coords, color="#ffffff", fill=False,
                       weight=1.5, opacity=0.4,
                       tooltip=region["name"]).add_to(m)

    # ── Gear-type legend ──
    legend_items = ""
    for gear, color in list(GEAR_COLORS.items())[:8]:
        legend_items += (f'<div><span style="background:{color};display:inline-block;'
                         f'width:14px;height:14px;margin-right:6px"></span>{gear}</div>')
    legend_html = f"""
    <div style="position:fixed; bottom:20px; right:10px; z-index:9999;
         background:rgba(0,0,0,0.75); color:white; padding:10px;
         border-radius:6px; font-family:monospace; font-size:11px">
      <b>Gear Type</b><br>{legend_items}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(output_path)
    return output_path


def plot_real_fleet_composition(region_key: str, output_path: str) -> str:
    """4-panel chart: gear type, flag state, monthly rhythm, gear intensity."""
    df    = load_region_fleet(region_key)
    stats = region_fishing_stats(region_key)
    region_name = REGIONS[region_key]["name"]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.patch.set_facecolor("#0d0d1a")
    fig.suptitle(f"GFW Real Fishing Data 2023 — {region_name}",
                 color="white", fontsize=14, fontweight="bold", y=0.98)

    PANEL_BG = "#12122a"
    for ax in axes.flat:
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors="white", labelsize=9)
        for sp in ax.spines.values():
            sp.set_edgecolor("#333")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    # ── 1. Top gear types by fishing hours ──
    ax = axes[0, 0]
    gear_fh = df.groupby("geartype")["fishing_hours"].sum().sort_values(ascending=True).tail(10)
    colors  = [GEAR_COLORS.get(g, "#999") for g in gear_fh.index]
    ax.barh(gear_fh.index, gear_fh.values / 1000, color=colors, edgecolor="#111")
    ax.set_title("Fishing Effort by Gear Type (thousand hrs)")
    ax.set_xlabel("Fishing hours (×1000)")

    # ── 2. Top 10 flag states by fishing hours ──
    ax = axes[0, 1]
    flag_fh = df.groupby("flag")["fishing_hours"].sum().sort_values(ascending=True).tail(10)
    cmap    = plt.cm.plasma(np.linspace(0.2, 0.9, len(flag_fh)))
    ax.barh(flag_fh.index, flag_fh.values / 1000, color=cmap, edgecolor="#111")
    ax.set_title("Fishing Effort by Flag State (thousand hrs)")
    ax.set_xlabel("Fishing hours (×1000)")

    # ── 3. Monthly fishing hours ──
    ax = axes[1, 0]
    monthly = df.groupby("month")["fishing_hours"].sum().reset_index()
    monthly["month_name"] = monthly["month"].map(MONTHS)
    ax.bar(monthly["month_name"], monthly["fishing_hours"] / 1000,
           color="#00aaff", edgecolor="#111", alpha=0.85)
    ax.set_title("Monthly Fishing Activity 2023")
    ax.set_xlabel("Month")
    ax.set_ylabel("Fishing hours (×1000)")

    # ── 4. Fishing intensity heatmap (lat/lon density) ──
    ax = axes[1, 1]
    grid = df.groupby(["cell_ll_lat", "cell_ll_lon"])["fishing_hours"].sum().reset_index()
    sc = ax.scatter(grid["cell_ll_lon"], grid["cell_ll_lat"],
                    c=np.log1p(grid["fishing_hours"]),
                    cmap="inferno", s=3, alpha=0.6, linewidths=0)
    ax.set_title("Fishing Intensity Distribution")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    cb = plt.colorbar(sc, ax=ax)
    cb.set_label("log(fishing hours)", color="white", fontsize=8)
    cb.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="white")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    return output_path


def plot_model_vs_reality(region_key: str, predictions_df: pd.DataFrame,
                           output_path: str) -> str:
    """
    Compare:
      - Left:  Our model's predicted vessel type distribution (synthetic data)
      - Right: Real GFW vessel type distribution in the same region
    """
    real_df     = load_region_fleet(region_key)
    region_name = REGIONS[region_key]["name"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#0d0d1a")
    fig.suptitle(f"Model Predictions vs. Real GFW Data — {region_name}",
                 color="white", fontsize=13, fontweight="bold")

    for ax in axes:
        ax.set_facecolor("#12122a")
        ax.tick_params(colors="white")
        for sp in ax.spines.values():
            sp.set_edgecolor("#333")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

    # ── Model predictions ──
    ax = axes[0]
    if "pred_vessel_type" in predictions_df.columns:
        model_counts = predictions_df["pred_vessel_type"].map(
            {"trawler":"trawlers", "longliner":"set_longlines",
             "purse_seiner":"other_purse_seines",
             "cargo":"cargo", "tanker":"tanker",
             "bulk_carrier":"bulk_carrier"}
        ).fillna(predictions_df["pred_vessel_type"]).value_counts()
        colors = [GEAR_COLORS.get(g, "#999") for g in model_counts.index]
        ax.barh(model_counts.index, model_counts.values, color=colors, edgecolor="#111")
        ax.set_title("Model: Predicted Vessel Types\n(Synthetic AIS Data)")
        ax.set_xlabel("Vessel count")
    else:
        ax.text(0.5, 0.5, "No predictions available", color="white",
                ha="center", va="center", transform=ax.transAxes)

    # ── Real GFW data ──
    ax = axes[1]
    real_gear = real_df.groupby("geartype")["mmsi_present"].sum().sort_values(ascending=True).tail(10)
    colors    = [GEAR_COLORS.get(g, "#999") for g in real_gear.index]
    ax.barh(real_gear.index, real_gear.values, color=colors, edgecolor="#111")
    ax.set_title("Reality: GFW Observed Fleet 2023\n(Real AIS via Global Fishing Watch)")
    ax.set_xlabel("Vessel-days observed")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    return output_path


def print_region_intelligence_report(region_key: str) -> None:
    """Print a human-readable intelligence summary for a region using real data."""
    stats = region_fishing_stats(region_key)
    region_name = REGIONS[region_key]["name"]

    print(f"\n{'═'*80}")
    print(f"  REAL-DATA INTELLIGENCE REPORT — {region_name.upper()}")
    print(f"  Source: Global Fishing Watch 2023 (CC-BY-NC 4.0)")
    print(f"{'═'*80}")
    print(f"  Total fishing hours:  {stats['total_fishing_hours']:>12,.0f}")
    print(f"  Total AIS hours:      {stats['total_hours']:>12,.0f}")
    print(f"  Fishing fraction:     {stats['fishing_fraction']:>12.1%}")
    print(f"  Unique 0.1° cells:    {stats['unique_cells']:>12,}")
    print(f"  Flag states present:  {stats['n_flag_states']:>12}")
    print(f"  Gear types detected:  {stats['n_gear_types']:>12}")

    print(f"\n  Top Flag States (by fishing hours):")
    for flag, fh in list(stats["top_flags"].items())[:8]:
        bar = "█" * int(fh / max(stats["top_flags"].values()) * 30)
        print(f"    {flag:5s}  {bar:<30}  {fh:>10,.0f} hrs")

    print(f"\n  Gear Types (by fishing hours):")
    for gear, fh in list(stats["top_geartypes"].items())[:8]:
        bar = "█" * int(fh / max(stats["top_geartypes"].values()) * 30)
        print(f"    {gear:<22}  {bar:<30}  {fh:>10,.0f} hrs")

    print(f"\n  Monthly Fishing Rhythm (2023):")
    monthly = stats["monthly_fishing"]
    max_m   = max(monthly.values()) if monthly else 1
    for m, fh in sorted(monthly.items()):
        bar = "█" * int(fh / max_m * 40)
        print(f"    {MONTHS.get(int(m), str(m)):3s}  {bar:<40}  {fh:>10,.0f}")

    print(f"\n  Top Fishing Hotspots (lat/lon):")
    for h in stats["peak_hotspots"][:5]:
        lat = h.get("cell_ll_lat", 0) + 0.05
        lon = h.get("cell_ll_lon", 0) + 0.05
        fh  = h.get("total_fishing_hours", 0)
        print(f"    {lat:>7.2f}°, {lon:>8.2f}°  →  {fh:>8,.0f} hrs")
    print()
