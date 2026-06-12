"""
Dataset Figure Generator
========================
Produces one figure per scenario type (13 total) plus an overview panel,
saved to outputs/tracking_dataset/figures/.

Each scenario figure shows all 20 geographic variants overlaid in a
normalized coordinate frame (centred on each variant's midpoint and
converted to nm), coloured by true_activity.

Usage:
    python generate_dataset_figures.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec

sys.path.insert(0, str(Path(__file__).parent))

# ── Style (match main project) ────────────────────────────────────────────────
BG     = "#0d1117"
PANEL  = "#161b22"
GRID   = "#21262d"
TEXT   = "#e6edf3"
ACCENT = "#58a6ff"
ORANGE = "#f0883e"
GREEN  = "#3fb950"
RED    = "#f85149"
PURPLE = "#bc8cff"
YELLOW = "#d29922"
TEAL   = "#39d353"

ACTIVITY_COLORS = {
    "fishing":       "#1f77b4",
    "transit":       GREEN,
    "anchored":      ORANGE,
    "loiter":        RED,
    "sts":           PURPLE,
    "bunkering":     YELLOW,
    "spoofed":       "#ff0055",
    "transshipment": TEAL,
    "port":          "#8c564b",
    "unknown":       "#6e7681",
}

TRACK_PALETTE = [
    "#58a6ff", "#f0883e", "#3fb950", "#f85149", "#bc8cff",
    "#39d353", "#d29922", "#ff7b72", "#79c0ff", "#ffa657",
    "#a5d6ff", "#ffd2a5", "#85e89d", "#ffb3b0", "#d2a8ff",
    "#79c0ff", "#e3b341", "#cf9fff", "#56d364", "#ffa198",
]

NM_PER_DEG = 60.0

FIGDIR = Path("outputs/tracking_dataset/figures")
FIGDIR.mkdir(parents=True, exist_ok=True)
DPI = 150


def _style(fig, axes=None):
    fig.patch.set_facecolor(BG)
    for ax in (axes if axes is not None else []):
        if ax is None:
            continue
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT, labelsize=7)
        ax.xaxis.label.set_color(TEXT)
        ax.yaxis.label.set_color(TEXT)
        ax.title.set_color(TEXT)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.grid(color=GRID, linewidth=0.4, alpha=0.6)


def _save(fig, name):
    path = FIGDIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"  saved {path}")
    return path


def _normalize_to_nm(df):
    """Centre each variant on its midpoint, convert degrees → nm."""
    frames = []
    for vid, grp in df.groupby("variant_id"):
        clat = grp["lat"].mean()
        clon = grp["lon"].mean()
        nm_x = (grp["lon"] - clon) * NM_PER_DEG * np.cos(np.radians(clat))
        nm_y = (grp["lat"] - clat) * NM_PER_DEG
        g2 = grp.copy()
        g2["nm_x"] = nm_x.values
        g2["nm_y"] = nm_y.values
        frames.append(g2)
    return pd.concat(frames, ignore_index=True)


SCENARIO_META = {
    "crossing_tracks": {
        "title":       "Crossing Tracks",
        "subtitle":    "Two vessels on converging bearings",
        "challenge":   (
            "A naive nearest-neighbour tracker swaps vessel identities at\n"
            "the crossing point when inter-vessel range drops below ~0.2 nm.\n"
            "Correct association requires bearing-rate and type continuity."
        ),
        "key_signals": ["COG divergence post-cross", "Speed continuity", "Type prior"],
        "n_vessels":   2,
        "duration":    "2 h",
    },
    "near_parallel": {
        "title":       "Near-Parallel Tracks",
        "subtitle":    "Two vessels <0.3 nm apart, same COG",
        "challenge":   (
            "Identical course and speed; the only discriminator is lateral\n"
            "offset. Classic ghost-track failure when the gate radius ≥ separation.\n"
            "Resolution requires fine-grained position accuracy."
        ),
        "key_signals": ["Lateral offset", "Ping-level range", "Type prior"],
        "n_vessels":   2,
        "duration":    "3 h",
    },
    "sts_rendezvous": {
        "title":       "STS Rendezvous",
        "subtitle":    "Converge → dwell → diverge",
        "challenge":   (
            "Vessels converge to <0.1 nm for 60 min then depart on\n"
            "opposite headings. Tracker must maintain separate IDs\n"
            "through a near-stationary mutual dwell phase."
        ),
        "key_signals": ["Inter-vessel range < 0.1 nm", "Near-zero SOG", "Symmetrical departure"],
        "n_vessels":   2,
        "duration":    "2.5 h",
    },
    "dark_reacquisition": {
        "title":       "Dark Period + Reacquisition",
        "subtitle":    "4-hour AIS gap, vessel reappears off dead-reckoned position",
        "challenge":   (
            "Vessel transmits, then goes dark for 4 h. When AIS resumes,\n"
            "position is 2–4 nm from the dead-reckoned mean. The tracker\n"
            "must decide: same vessel, or new contact?"
        ),
        "key_signals": ["Dead-reckoning cone", "Position jump on reacquisition", "Speed plausibility"],
        "n_vessels":   1,
        "duration":    "6.5 h (incl. gap)",
    },
    "trawling_pattern": {
        "title":       "Trawling S-Curve Pattern",
        "subtitle":    "Paired haul legs + sharp 180° turns, then transit",
        "challenge":   (
            "Fishing S-curves at 3–4 kn are followed by a 10 kn transit.\n"
            "Activity label changes mid-track; a static-window classifier\n"
            "misclassifies the transition point."
        ),
        "key_signals": ["SOG bimodal (3 kn / 10 kn)", "Periodic 180° turn", "Nav-status change"],
        "n_vessels":   1,
        "duration":    "~2 h",
    },
    "coordinated_fleet": {
        "title":       "Coordinated Purse-Seine Fleet",
        "subtitle":    "6 vessels converge and encircle within 0.2 nm",
        "challenge":   (
            "6 purse seiners start in a 0.8 nm arc, converge, then orbit\n"
            "a common centre at ≤0.2 nm separation. Track-to-track\n"
            "correlation fails at this density without type-level gating."
        ),
        "key_signals": ["Swarm convergence geometry", "Circular orbit", "Uniform vessel type"],
        "n_vessels":   6,
        "duration":    "1.2 h",
    },
    "mmsi_clone": {
        "title":       "MMSI Cloning / Identity Spoofing",
        "subtitle":    "Same MMSI broadcast from two positions simultaneously",
        "challenge":   (
            "One MMSI produces two simultaneous, physically incompatible\n"
            "position reports 15 nm apart. A naive tracker splits into\n"
            "two tracks or drops one; neither is correct."
        ),
        "key_signals": ["Duplicate MMSI", "Impossible positional jump rate", "Type/SOG inconsistency"],
        "n_vessels":   2,
        "duration":    "2 h",
    },
    "evasive_maneuvering": {
        "title":       "Evasive Maneuvering",
        "subtitle":    "Angular rates >20°/min, irregular heading changes",
        "challenge":   (
            "Sharp, unpredictable turns break constant-velocity track\n"
            "prediction. IMM / manoeuvre-adaptive filters required;\n"
            "a single Kalman gate drops the track after the first turn."
        ),
        "key_signals": ["Turn rate > 20°/min", "Speed changes at turns", "No nav-status justification"],
        "n_vessels":   1,
        "duration":    "1.1 h",
    },
    "speed_jump_noisy": {
        "title":       "Multi-Sensor Noisy Track + Speed Jump",
        "subtitle":    "AIS gaps, outlier pings, sensor-type transitions",
        "challenge":   (
            "AIS, EO, and radar pings interleave; 15% of rows are dark;\n"
            "4 outlier positions are injected (3–8 nm error). A genuine\n"
            "activity transition (fishing→transit→anchor) occurs mid-track."
        ),
        "key_signals": ["Sensor-type heterogeneity", "Outlier positions", "Multi-phase SOG"],
        "n_vessels":   1,
        "duration":    "3.7 h",
    },
    "dense_cluster": {
        "title":       "Dense Vessel Cluster",
        "subtitle":    "12 vessels in a 0.5 nm radius",
        "challenge":   (
            "8 fishing, 2 support, 1 cargo, 1 tug all operating within\n"
            "0.5 nm. Association is at sensor resolution; only vessel-type\n"
            "priors and speed-profile differences allow disambiguation."
        ),
        "key_signals": ["12-vessel association problem", "Mixed vessel types", "Overlapping uncertainty gates"],
        "n_vessels":   12,
        "duration":    "1 h",
    },
    "position_spoofing": {
        "title":       "GPS Position Spoofing",
        "subtitle":    "AIS reports frozen position; satellite reveals true track",
        "challenge":   (
            "AIS broadcast freezes position for 3 h (vessel reports\n"
            "anchored) while the vessel actually transits at 14 kn.\n"
            "Cross-sensor comparison exposes the inconsistency."
        ),
        "key_signals": ["Zero reported SOG vs. observed motion", "Impossible position jump on resume", "Sensor disagreement"],
        "n_vessels":   1,
        "duration":    "6 h",
    },
    "track_fragmentation": {
        "title":       "Track Fragmentation",
        "subtitle":    "6 short AIS bursts separated by 20–60 min gaps",
        "challenge":   (
            "A single vessel appears as 6 disconnected fragments, each\n"
            "too short for confident activity classification. Stitching\n"
            "requires dead-reckoning plausibility across each gap."
        ),
        "key_signals": ["Fragment stitching via DR", "Short bursts (3–7 pings)", "Gap duration 20–60 min"],
        "n_vessels":   1,
        "duration":    "6.7 h",
    },
    "bunkering_rendezvous": {
        "title":       "Bunkering Rendezvous",
        "subtitle":    "Bunker barge meets cargo in port approach anchorage",
        "challenge":   (
            "Barge and cargo are near-stationary for 90 min, triggering\n"
            "false STS alerts and confusion with anchored vessels.\n"
            "High port-approach density complicates track assignment."
        ),
        "key_signals": ["Near-stationary pair", "Background traffic clutter", "False STS signature"],
        "n_vessels":   5,
        "duration":    "3.8 h",
    },
}


def _make_scenario_figure(scenario_name: str, df: pd.DataFrame) -> Path:
    meta = SCENARIO_META.get(scenario_name, {})
    title = meta.get("title", scenario_name)

    df_nm = _normalize_to_nm(df)
    live = df_nm[~df_nm["is_dark"]]
    dark = df_nm[df_nm["is_dark"]]

    activities = sorted(live["true_activity"].dropna().unique())
    n_variants = df["variant_id"].nunique()

    fig = plt.figure(figsize=(14, 7))
    _style(fig)
    gs = GridSpec(1, 3, figure=fig, left=0.05, right=0.97,
                  top=0.88, bottom=0.10, wspace=0.35)

    ax_main  = fig.add_subplot(gs[0, :2])
    ax_stats = fig.add_subplot(gs[0, 2])
    _style(fig, [ax_main, ax_stats])

    # ── Main panel: all variants overlaid ─────────────────────────────────────
    track_ids = sorted(live["track_id"].unique())

    for vid, vgrp in live.groupby("variant_id"):
        alpha = 0.55
        lw = 0.9
        for tid, tgrp in vgrp.groupby("track_id"):
            tgrp_s = tgrp.sort_values("timestamp")
            color = ACTIVITY_COLORS.get(tgrp_s["true_activity"].iloc[0], ACCENT)
            ax_main.plot(tgrp_s["nm_x"], tgrp_s["nm_y"],
                         color=color, alpha=alpha, linewidth=lw, zorder=2)
            # Mark start dot
            ax_main.scatter(tgrp_s["nm_x"].iloc[0], tgrp_s["nm_y"].iloc[0],
                            color=color, s=12, alpha=alpha, zorder=3)

    # Dark gap rows as dashed grey
    if len(dark) > 0:
        for vid, vgrp in dark.groupby("variant_id"):
            vgrp_s = vgrp.sort_values("timestamp")
            ax_main.plot(vgrp_s["nm_x"], vgrp_s["nm_y"],
                         color="#555566", alpha=0.3, linewidth=0.6,
                         linestyle="--", zorder=1)

    ax_main.set_xlabel("East  (nm)", color=TEXT, fontsize=8)
    ax_main.set_ylabel("North  (nm)", color=TEXT, fontsize=8)
    ax_main.set_aspect("equal", adjustable="datalim")

    # Variant count watermark
    ax_main.text(0.98, 0.02, f"{n_variants} variants overlaid",
                 transform=ax_main.transAxes, ha="right", va="bottom",
                 color="#6e7681", fontsize=7)

    # Activity legend
    legend_handles = [
        Line2D([0], [0], color=ACTIVITY_COLORS.get(a, ACCENT), linewidth=2, label=a)
        for a in activities
    ]
    if dark["is_dark"].any():
        legend_handles.append(
            Line2D([0], [0], color="#555566", linewidth=1,
                   linestyle="--", label="dark gap (DR)")
        )
    ax_main.legend(handles=legend_handles, loc="upper left",
                   fontsize=7, framealpha=0.3,
                   facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)

    # ── Right panel: stats + challenge ────────────────────────────────────────
    ax_stats.set_axis_off()

    stats_text_parts = []

    # Stats block
    live_pings  = int((~df["is_dark"]).sum())
    dark_pings  = int(df["is_dark"].sum())
    n_vessels   = int(df["mmsi"].nunique())
    n_tracks    = int(df["track_id"].nunique())
    sensors     = sorted(df["sensor_type"].dropna().unique())
    vtypes      = sorted(df["vessel_type"].dropna().unique())
    acts        = sorted(df["true_activity"].dropna().unique())
    ts          = pd.to_datetime(df["timestamp"])
    dur_min     = float((ts.max() - ts.min()).total_seconds() / 60 / n_variants)

    stat_lines = [
        ("Scenario type",    scenario_name.replace("_", " ")),
        ("Variants",         str(n_variants)),
        ("Total pings",      f"{live_pings:,} live  +  {dark_pings:,} DR"),
        ("Vessels / MMSI",   str(n_vessels // n_variants)),
        ("Track IDs",        str(n_tracks // max(n_variants, 1))),
        ("Duration / variant", f"{dur_min:.0f} min"),
        ("Sensor types",     ", ".join(sensors)),
        ("Vessel types",     "\n                       ".join(vtypes)),
        ("Activities",       "\n                       ".join(acts)),
    ]

    y = 0.97
    for label, val in stat_lines:
        ax_stats.text(0.0, y, f"{label}:", color="#8b949e",
                      fontsize=7.5, transform=ax_stats.transAxes, va="top",
                      fontweight="bold")
        ax_stats.text(0.42, y, val, color=TEXT,
                      fontsize=7.5, transform=ax_stats.transAxes, va="top")
        y -= 0.088

    # Challenge section
    y -= 0.03
    ax_stats.text(0.0, y, "Tracking challenge:", color=ORANGE,
                  fontsize=8, transform=ax_stats.transAxes, va="top",
                  fontweight="bold")
    y -= 0.10
    challenge = meta.get("challenge", "")
    ax_stats.text(0.0, y, challenge, color=TEXT,
                  fontsize=7, transform=ax_stats.transAxes, va="top",
                  wrap=True, linespacing=1.5)

    y -= (challenge.count("\n") + 1) * 0.085 + 0.06
    key_signals = meta.get("key_signals", [])
    if key_signals:
        ax_stats.text(0.0, y, "Key discriminators:", color=ACCENT,
                      fontsize=7.5, transform=ax_stats.transAxes, va="top",
                      fontweight="bold")
        y -= 0.075
        for sig in key_signals:
            ax_stats.text(0.04, y, f"• {sig}", color=TEXT,
                          fontsize=7, transform=ax_stats.transAxes, va="top")
            y -= 0.07

    # ── Title ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.96, title,
             ha="center", va="top", color=TEXT,
             fontsize=15, fontweight="bold")
    subtitle = meta.get("subtitle", "")
    fig.text(0.5, 0.925, subtitle,
             ha="center", va="top", color="#8b949e", fontsize=9)

    fname = f"scenario_{scenario_name}.png"
    return _save(fig, fname)


def _make_overview_panel(dataset_dir: Path) -> Path:
    """2-row × 7-col small-multiples overview of all 13 scenarios."""
    scenarios_order = list(SCENARIO_META.keys())
    n = len(scenarios_order)
    ncols = 7
    nrows = 2

    fig, axes = plt.subplots(nrows, ncols, figsize=(22, 7))
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.88,
                        bottom=0.05, hspace=0.45, wspace=0.35)

    for idx, sname in enumerate(scenarios_order):
        row, col = divmod(idx, ncols)
        ax = axes[row][col]
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.tick_params(colors=TEXT, labelsize=5.5)
        ax.grid(color=GRID, linewidth=0.3, alpha=0.5)

        # Load the per-type merged CSV
        csv_path = dataset_dir / f"{sname}_all_variants.csv"
        if not csv_path.exists():
            ax.set_title(sname, color=RED, fontsize=6)
            continue

        df = pd.read_csv(csv_path)
        df_nm = _normalize_to_nm(df)
        live = df_nm[~df_nm["is_dark"]]
        dark = df_nm[df_nm["is_dark"]]

        for vid, vgrp in live.groupby("variant_id"):
            for tid, tgrp in vgrp.groupby("track_id"):
                tgrp_s = tgrp.sort_values("timestamp")
                color = ACTIVITY_COLORS.get(tgrp_s["true_activity"].iloc[0], ACCENT)
                ax.plot(tgrp_s["nm_x"], tgrp_s["nm_y"],
                        color=color, alpha=0.45, linewidth=0.5, zorder=2)

        if len(dark):
            for vid, vgrp in dark.groupby("variant_id"):
                vgrp_s = vgrp.sort_values("timestamp")
                ax.plot(vgrp_s["nm_x"], vgrp_s["nm_y"],
                        color="#444455", alpha=0.2, linewidth=0.4,
                        linestyle="--", zorder=1)

        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title(SCENARIO_META[sname]["title"],
                     color=TEXT, fontsize=6.5, pad=3)
        ax.set_xticks([])
        ax.set_yticks([])

    # Hide last unused subplot if any
    used = len(scenarios_order)
    total = nrows * ncols
    for extra in range(used, total):
        r, c = divmod(extra, ncols)
        axes[r][c].set_visible(False)

    fig.text(0.5, 0.97, "Tracking Challenge Dataset — All 13 Scenario Types",
             ha="center", va="top", color=TEXT, fontsize=14, fontweight="bold")
    fig.text(0.5, 0.935, "20 geographic variants per type  ·  track shapes normalised to nautical-mile centred frame",
             ha="center", va="top", color="#8b949e", fontsize=8)

    # Shared activity legend
    acts_shown = ["fishing", "transit", "anchored", "sts", "bunkering",
                  "spoofed", "loiter"]
    legend_handles = [
        mpatches.Patch(color=ACTIVITY_COLORS[a], label=a, alpha=0.8)
        for a in acts_shown
    ]
    legend_handles.append(
        plt.Line2D([0],[0], color="#444455", linewidth=1,
                   linestyle="--", label="dark gap (DR)")
    )
    fig.legend(handles=legend_handles, loc="lower center",
               ncol=len(legend_handles), fontsize=7,
               facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
               framealpha=0.6, bbox_to_anchor=(0.5, -0.01))

    return _save(fig, "overview_all_scenarios.png")


def main():
    dataset_dir = Path("outputs/tracking_dataset")
    if not dataset_dir.exists():
        print("ERROR: Run build_tracking_dataset.py first.")
        return

    print(f"Writing figures to {FIGDIR}/\n")

    # Generate one figure per scenario
    for sname, meta in SCENARIO_META.items():
        csv_path = dataset_dir / f"{sname}_all_variants.csv"
        if not csv_path.exists():
            print(f"  SKIP {sname} (CSV not found)")
            continue
        print(f"  {meta['title']} …")
        df = pd.read_csv(csv_path)
        _make_scenario_figure(sname, df)

    # Overview panel
    print("\n  Overview panel …")
    _make_overview_panel(dataset_dir)

    print(f"\nDone. {len(SCENARIO_META) + 1} figures written to {FIGDIR}/")


if __name__ == "__main__":
    main()
