"""
Tracking Benchmark Scenario Generator

Produces synthetic AIS/multi-sensor tracks for the canonically difficult
tracking problems used in benchmarking data association algorithms:

  1.  Crossing Tracks          – two vessels cross; naive proximity causes ID swap
  2.  Near-Parallel Tracks     – two vessels <0.3 nm apart, same course
  3.  STS Rendezvous           – converge → dwell → separate (tanker + supply)
  4.  Dark Reacquisition       – AIS gap + dead-reckoning cone + reacquire
  5.  Trawling Pattern         – fishing S-curves / back-and-forth hauls
  6.  Coordinated Fishing Fleet– 6 purse seiners in ≤1 nm radius, interleaving
  7.  MMSI Clone               – same MMSI broadcast from two positions
  8.  Evasive Maneuvering      – sharp turns mimicking evasion, high angular acc.
  9.  Speed-Jump Noisy Track   – outlier pings + sensor gaps + occasional fixes
  10. Dense Cluster            – 12 vessels in 0.5 nm; association at resolution limit

Each scenario returns a DataFrame with:
    mmsi, timestamp, lat, lon, sog, cog, heading,
    sensor_type, true_activity, vessel_type, nav_status,
    scenario, track_id, is_dark

Usage:
    from src.tracking_scenarios import generate_all_scenarios
    scenarios = generate_all_scenarios()
    for name, df in scenarios.items():
        print(name, df.shape)
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional

_RNG = np.random.default_rng(2024)

_NM_PER_DEG_LAT = 60.0
_T0 = pd.Timestamp("2024-01-15 06:00:00", tz="UTC")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _propagate(lat0, lon0, cog_deg, sog_kn, dt_min, n_steps,
               cog_noise=0.0, sog_noise=0.0, rng=_RNG):
    """Dead-reckon a track. Returns (lats, lons, cogs, sogs)."""
    lats  = np.zeros(n_steps + 1)
    lons  = np.zeros(n_steps + 1)
    cogs  = np.zeros(n_steps + 1)
    sogs  = np.zeros(n_steps + 1)
    lats[0], lons[0] = lat0, lon0
    cogs[0] = cog_deg % 360
    sogs[0] = sog_kn

    for i in range(n_steps):
        c = cogs[i] + rng.normal(0, cog_noise)
        s = max(0.0, sogs[i] + rng.normal(0, sog_noise))
        rad  = np.radians(c % 360)
        dist = s * dt_min / 60.0   # nm
        clat = np.cos(np.radians(lats[i]))
        lats[i+1] = lats[i] + (dist * np.cos(rad)) / _NM_PER_DEG_LAT
        lons[i+1] = lons[i] + (dist * np.sin(rad)) / (_NM_PER_DEG_LAT * clat)
        cogs[i+1] = c % 360
        sogs[i+1] = s
    return lats, lons, cogs, sogs


def _track_df(mmsi, lats, lons, cogs, sogs, t0, dt_min,
              sensor="ais", activity="transit", vtype="cargo",
              nav_status=0, scenario="", track_id=None, is_dark=None):
    n = len(lats)
    ts = [t0 + pd.Timedelta(minutes=i * dt_min) for i in range(n)]
    return pd.DataFrame({
        "mmsi":          mmsi,
        "timestamp":     ts,
        "lat":           lats,
        "lon":           lons,
        "sog":           sogs,
        "cog":           cogs,
        "heading":       cogs,
        "sensor_type":   sensor,
        "true_activity": activity,
        "vessel_type":   vtype,
        "nav_status":    nav_status,
        "scenario":      scenario,
        "track_id":      track_id if track_id is not None else mmsi,
        "is_dark":       is_dark if is_dark is not None else False,
    })


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 1: Crossing Tracks
# ══════════════════════════════════════════════════════════════════════════════

def scenario_crossing_tracks() -> pd.DataFrame:
    """
    Two cargo vessels cross at nearly right angles.
    At t=30 min they are within 0.2 nm.  A naive nearest-neighbour tracker
    swaps their identities after the crossing.
    """
    dt = 2   # minutes per ping
    n  = 60  # 2-hour scenario

    # Track A: heading NE at 12 kn, starts SW of crossing
    la, lona, ca, sa = _propagate(1.00, 103.50, cog_deg=45, sog_kn=12,
                                   dt_min=dt, n_steps=n, cog_noise=0.5)
    # Track B: heading NW at 10 kn, starts SE of crossing
    lb, lonb, cb, sb = _propagate(1.00, 103.80, cog_deg=315, sog_kn=10,
                                   dt_min=dt, n_steps=n, cog_noise=0.5)

    dfA = _track_df(111_001_001, la, lona, ca, sa, _T0, dt,
                    vtype="cargo", activity="transit", scenario="crossing_tracks",
                    track_id="A")
    dfB = _track_df(111_001_002, lb, lonb, cb, sb, _T0, dt,
                    vtype="tanker", activity="transit", scenario="crossing_tracks",
                    track_id="B")
    return pd.concat([dfA, dfB], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 2: Near-Parallel Tracks
# ══════════════════════════════════════════════════════════════════════════════

def scenario_near_parallel() -> pd.DataFrame:
    """
    Two vessels moving in the same direction (N, 10 kn) separated by only
    ~0.25 nm (≈450 m).  Identical speed/course; the only separator is
    their lateral offset.  Classic ghost-track scenario.
    """
    dt = 3
    n  = 60

    # Lateral offset: 0.25 nm in longitude ≈ 0.25/60° at equator
    offset = 0.25 / _NM_PER_DEG_LAT   # degrees

    la, lona, ca, sa = _propagate(1.00, 103.60, cog_deg=0, sog_kn=10,
                                   dt_min=dt, n_steps=n, cog_noise=0.3, sog_noise=0.2)
    lb, lonb, cb, sb = _propagate(1.00, 103.60 + offset, cog_deg=0, sog_kn=10.3,
                                   dt_min=dt, n_steps=n, cog_noise=0.4, sog_noise=0.2)

    dfA = _track_df(111_002_001, la, lona, ca, sa, _T0, dt,
                    vtype="cargo", activity="transit", scenario="near_parallel",
                    track_id="A")
    dfB = _track_df(111_002_002, lb, lonb, cb, sb, _T0, dt,
                    vtype="cargo", activity="transit", scenario="near_parallel",
                    track_id="B")
    return pd.concat([dfA, dfB], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 3: STS Rendezvous
# ══════════════════════════════════════════════════════════════════════════════

def scenario_sts_rendezvous() -> pd.DataFrame:
    """
    Tanker and supply vessel converge over 45 min, hold position together
    for 60 min (STS transfer), then diverge.  The dwell phase is a strong
    STS classifier trigger.
    """
    dt = 2

    # ── Approach phase (45 min = 22 steps) ──────────────────────────────────
    n_approach = 22
    la_ap, lona_ap, ca_ap, sa_ap = _propagate(
        1.50, 103.20, cog_deg=90, sog_kn=8, dt_min=dt, n_steps=n_approach)
    lb_ap, lonb_ap, cb_ap, sb_ap = _propagate(
        1.52, 103.70, cog_deg=270, sog_kn=6, dt_min=dt, n_steps=n_approach)

    # ── Dwell phase (60 min = 30 steps, both near-stationary) ────────────────
    n_dwell = 30
    t_dwell = _T0 + pd.Timedelta(minutes=n_approach * dt)
    la_dw, lona_dw, ca_dw, sa_dw = _propagate(
        la_ap[-1], lona_ap[-1], cog_deg=90, sog_kn=0.3,
        dt_min=dt, n_steps=n_dwell, cog_noise=30, sog_noise=0.2)
    lb_dw, lonb_dw, cb_dw, sb_dw = _propagate(
        lb_ap[-1], lonb_ap[-1], cog_deg=270, sog_kn=0.3,
        dt_min=dt, n_steps=n_dwell, cog_noise=30, sog_noise=0.2)

    # ── Departure phase (45 min = 22 steps) ──────────────────────────────────
    n_depart = 22
    t_depart = t_dwell + pd.Timedelta(minutes=n_dwell * dt)
    la_de, lona_de, ca_de, sa_de = _propagate(
        la_dw[-1], lona_dw[-1], cog_deg=270, sog_kn=8,
        dt_min=dt, n_steps=n_depart)
    lb_de, lonb_de, cb_de, sb_de = _propagate(
        lb_dw[-1], lonb_dw[-1], cog_deg=90, sog_kn=6,
        dt_min=dt, n_steps=n_depart)

    # ── Concatenate phases ────────────────────────────────────────────────────
    def _concat(arrs): return np.concatenate(arrs)
    la_all   = _concat([la_ap, la_dw[1:], la_de[1:]])
    lona_all = _concat([lona_ap, lona_dw[1:], lona_de[1:]])
    ca_all   = _concat([ca_ap, ca_dw[1:], ca_de[1:]])
    sa_all   = _concat([sa_ap, sa_dw[1:], sa_de[1:]])

    lb_all   = _concat([lb_ap, lb_dw[1:], lb_de[1:]])
    lonb_all = _concat([lonb_ap, lonb_dw[1:], lonb_de[1:]])
    cb_all   = _concat([cb_ap, cb_dw[1:], cb_de[1:]])
    sb_all   = _concat([sb_ap, sb_dw[1:], sb_de[1:]])

    n_tot = len(la_all)
    # la_ap has n_approach+1 pts; la_dw[1:] has n_dwell pts; la_de[1:] has n_depart pts
    act_a = (["transit"] * (n_approach + 1) +
             ["sts"]     * n_dwell +
             ["transit"] * n_depart)[:n_tot]
    act_b = act_a[:]

    def _mk(mmsi, lats, lons, cogs, sogs, acts, vtype):
        ts = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(len(lats))]
        return pd.DataFrame({
            "mmsi": mmsi, "timestamp": ts, "lat": lats, "lon": lons,
            "sog": sogs, "cog": cogs, "heading": cogs,
            "sensor_type": "ais", "true_activity": acts,
            "vessel_type": vtype, "nav_status": 0,
            "scenario": "sts_rendezvous",
            "track_id": str(mmsi),
            "is_dark": False,
        })

    dfA = _mk(111_003_001, la_all, lona_all, ca_all, sa_all, act_a, "tanker")
    dfB = _mk(111_003_002, lb_all, lonb_all, cb_all, sb_all, act_b, "support_vessel")
    return pd.concat([dfA, dfB], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 4: Dark Reacquisition
# ══════════════════════════════════════════════════════════════════════════════

def scenario_dark_reacquisition() -> pd.DataFrame:
    """
    Fishing vessel transits, turns AIS off for 4 hours, then reappears
    shifted from the dead-reckoned mean position.  Demonstrates custody gap
    and uncertainty cone.
    """
    dt = 5

    # Pre-dark leg (90 min)
    n_pre = 18
    lp, lonp, cp, sp = _propagate(3.00, 103.00, cog_deg=60, sog_kn=8,
                                   dt_min=dt, n_steps=n_pre, cog_noise=2.0)

    # Post-dark leg (60 min, reacquired ~3nm from dead-reckoned mean)
    n_post = 12
    la0 = lp[-1] + 0.035   # ~2 nm N from dead-reckoned position
    lono0 = lonp[-1] + 0.04
    lpo, lonpo, cpo, spo = _propagate(la0, lono0, cog_deg=55, sog_kn=7,
                                       dt_min=dt, n_steps=n_post, cog_noise=2.0)

    t_reacquire = _T0 + pd.Timedelta(minutes=n_pre * dt + 240)  # +4h dark

    def _mk(lats, lons, cogs, sogs, t0_row, acts, dark):
        ts = [t0_row + pd.Timedelta(minutes=i * dt) for i in range(len(lats))]
        return pd.DataFrame({
            "mmsi": 111_004_001, "timestamp": ts, "lat": lats, "lon": lons,
            "sog": sogs, "cog": cogs, "heading": cogs,
            "sensor_type": ["ais"] * len(lats),
            "true_activity": acts, "vessel_type": "fishing",
            "nav_status": 7, "scenario": "dark_reacquisition",
            "track_id": "A",
            "is_dark": dark,
        })

    dfP  = _mk(lp,  lonp,  cp,  sp,  _T0,         ["fishing"] * len(lp),  [False]*len(lp))
    dfPo = _mk(lpo, lonpo, cpo, spo, t_reacquire, ["fishing"] * len(lpo), [False]*len(lpo))

    # Dark gap rows (for visualisation; sensor=none)
    gap_ts = [_T0 + pd.Timedelta(minutes=n_pre*dt + i*30) for i in range(9)]
    gap_lats = np.linspace(lp[-1], la0, 9)
    gap_lons = np.linspace(lonp[-1], lono0, 9)
    dfGap = pd.DataFrame({
        "mmsi": 111_004_001, "timestamp": gap_ts,
        "lat": gap_lats, "lon": gap_lons,
        "sog": np.full(9, np.nan), "cog": np.full(9, np.nan), "heading": np.full(9, np.nan),
        "sensor_type": "none", "true_activity": "transit",
        "vessel_type": "fishing", "nav_status": np.nan,
        "scenario": "dark_reacquisition", "track_id": "A",
        "is_dark": True,
    })

    return pd.concat([dfP, dfGap, dfPo], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 5: Trawling Pattern
# ══════════════════════════════════════════════════════════════════════════════

def scenario_trawling_pattern() -> pd.DataFrame:
    """
    Trawler executing classic paired back-and-forth haul pattern.
    S-curves with slow speed (3-4 kn) and regular 180° turns every ~20 min.
    Followed by a transit leg at 10 kn (going to offload).
    """
    dt = 2
    # 5 haul pairs, each 20 min out + 20 min back
    rows = []
    lat0, lon0 = 4.00, 99.50
    cog = 90.0
    t_cur = _T0

    for haul in range(5):
        # Tow leg
        n_tow = 10
        lt, lont, ct, st = _propagate(lat0, lon0, cog_deg=cog, sog_kn=3.5,
                                       dt_min=dt, n_steps=n_tow, cog_noise=5, sog_noise=0.4)
        rows.append(pd.DataFrame({
            "mmsi": 111_005_001,
            "timestamp": [t_cur + pd.Timedelta(minutes=i*dt) for i in range(len(lt))],
            "lat": lt, "lon": lont, "sog": st, "cog": ct, "heading": ct,
            "sensor_type": "ais", "true_activity": "fishing",
            "vessel_type": "trawler", "nav_status": 7,
            "scenario": "trawling_pattern", "track_id": "A", "is_dark": False,
        }))
        t_cur += pd.Timedelta(minutes=n_tow * dt)
        lat0, lon0 = lt[-1], lont[-1]

        # Turn (sharp 180° over 4 min)
        n_turn = 3
        cog_turn = cog + 180
        lt2, lont2, ct2, st2 = _propagate(lat0, lon0, cog_deg=cog_turn, sog_kn=3.5,
                                           dt_min=dt, n_steps=n_turn, cog_noise=30)
        rows.append(pd.DataFrame({
            "mmsi": 111_005_001,
            "timestamp": [t_cur + pd.Timedelta(minutes=i*dt) for i in range(len(lt2))],
            "lat": lt2, "lon": lont2, "sog": st2, "cog": ct2, "heading": ct2,
            "sensor_type": "ais", "true_activity": "fishing",
            "vessel_type": "trawler", "nav_status": 7,
            "scenario": "trawling_pattern", "track_id": "A", "is_dark": False,
        }))
        t_cur += pd.Timedelta(minutes=n_turn * dt)
        lat0, lon0 = lt2[-1], lont2[-1]
        cog = (cog + 180) % 360

    # Transit to port
    n_transit = 20
    lt3, lont3, ct3, st3 = _propagate(lat0, lon0, cog_deg=150, sog_kn=10,
                                       dt_min=dt, n_steps=n_transit, cog_noise=1)
    rows.append(pd.DataFrame({
        "mmsi": 111_005_001,
        "timestamp": [t_cur + pd.Timedelta(minutes=i*dt) for i in range(len(lt3))],
        "lat": lt3, "lon": lont3, "sog": st3, "cog": ct3, "heading": ct3,
        "sensor_type": "ais", "true_activity": "transit",
        "vessel_type": "trawler", "nav_status": 0,
        "scenario": "trawling_pattern", "track_id": "A", "is_dark": False,
    }))

    return pd.concat(rows, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 6: Coordinated Fishing Fleet
# ══════════════════════════════════════════════════════════════════════════════

def scenario_coordinated_fleet() -> pd.DataFrame:
    """
    6 purse seiners executing a coordinated encirclement manoeuvre:
    they start spread in a 0.8 nm arc, converge on a bait ball centre,
    then encircle it (all vessels within 0.2 nm of each other).
    Classic challenge for track-to-track correlation at swarm density.
    """
    dt = 2
    n_converge = 15
    n_circle   = 20

    centre_lat, centre_lon = 5.00, 100.00
    n_vessels   = 6
    dfs = []
    rng2 = np.random.default_rng(77)

    for i in range(n_vessels):
        angle = (360 / n_vessels) * i
        r_deg = 0.8 / _NM_PER_DEG_LAT
        start_lat = centre_lat + r_deg * np.cos(np.radians(angle))
        start_lon = centre_lon + r_deg * np.sin(np.radians(angle)) / np.cos(np.radians(centre_lat))

        # Converge toward centre
        head_to_centre = (np.degrees(np.arctan2(
            (centre_lon - start_lon) * np.cos(np.radians(start_lat)),
            centre_lat - start_lat
        )) + 360) % 360
        lc, lonc, cc, sc = _propagate(start_lat, start_lon,
                                       cog_deg=head_to_centre, sog_kn=6.0,
                                       dt_min=dt, n_steps=n_converge,
                                       cog_noise=2, sog_noise=0.3, rng=rng2)

        # Circle the bait ball
        r_circ = 0.15 / _NM_PER_DEG_LAT
        phase  = angle + 45 * i   # staggered start on circle
        lcirc  = np.array([
            centre_lat + r_circ * np.cos(np.radians(phase + j * (360 / n_circle)))
            for j in range(n_circle + 1)
        ])
        loncirc = np.array([
            centre_lon + r_circ * np.sin(np.radians(phase + j * (360 / n_circle)))
                         / np.cos(np.radians(centre_lat))
            for j in range(n_circle + 1)
        ])
        circ_cog = np.array([
            (np.degrees(np.arctan2(
                (loncirc[j+1] - loncirc[j]) * np.cos(np.radians(lcirc[j])),
                lcirc[j+1] - lcirc[j]
            )) + 360) % 360
            if j < n_circle else 0
            for j in range(n_circle + 1)
        ])
        circ_sog = np.full(n_circle + 1, 3.0)

        t0_circ = _T0 + pd.Timedelta(minutes=n_converge * dt)
        ts_conv = [_T0 + pd.Timedelta(minutes=j * dt) for j in range(len(lc))]
        ts_circ = [t0_circ + pd.Timedelta(minutes=j * dt) for j in range(len(lcirc))]

        df_conv = pd.DataFrame({
            "mmsi": 111_006_000 + i, "timestamp": ts_conv,
            "lat": lc, "lon": lonc, "sog": sc, "cog": cc, "heading": cc,
            "sensor_type": "ais", "true_activity": "transit",
            "vessel_type": "purse_seiner", "nav_status": 0,
            "scenario": "coordinated_fleet", "track_id": str(i), "is_dark": False,
        })
        df_circ = pd.DataFrame({
            "mmsi": 111_006_000 + i, "timestamp": ts_circ,
            "lat": lcirc, "lon": loncirc, "sog": circ_sog, "cog": circ_cog,
            "heading": circ_cog,
            "sensor_type": "ais", "true_activity": "fishing",
            "vessel_type": "purse_seiner", "nav_status": 7,
            "scenario": "coordinated_fleet", "track_id": str(i), "is_dark": False,
        })
        dfs.extend([df_conv, df_circ])

    return pd.concat(dfs, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 7: MMSI Clone
# ══════════════════════════════════════════════════════════════════════════════

def scenario_mmsi_clone() -> pd.DataFrame:
    """
    One MMSI (the cloner) duplicates a legitimate vessel's MMSI to mask
    identity.  Both vessels broadcast the same MMSI simultaneously.
    The tracker sees a single MMSI with two conflicting positions.
    """
    dt = 3
    n  = 40

    # Legitimate vessel (slow, heading north through Malacca)
    la, lona, ca, sa = _propagate(1.00, 103.70, cog_deg=350, sog_kn=12,
                                   dt_min=dt, n_steps=n, cog_noise=1)
    # Clone: fishing vessel, heading east at 5 kn, 15 nm away
    r_deg = 15 / _NM_PER_DEG_LAT
    lb, lonb, cb, sb = _propagate(1.00 + r_deg, 103.50, cog_deg=90, sog_kn=5,
                                   dt_min=dt, n_steps=n, cog_noise=10, sog_noise=1)

    CLONED_MMSI = 111_007_001
    dfA = _track_df(CLONED_MMSI, la, lona, ca, sa, _T0, dt,
                    vtype="cargo", activity="transit", scenario="mmsi_clone",
                    track_id="legitimate")
    dfB = _track_df(CLONED_MMSI, lb, lonb, cb, sb, _T0, dt,
                    vtype="fishing", activity="fishing", scenario="mmsi_clone",
                    track_id="clone")
    # Mark clone with different nav_status to help the classifier
    dfB["nav_status"] = 7
    return pd.concat([dfA, dfB], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 8: Evasive Maneuvering
# ══════════════════════════════════════════════════════════════════════════════

def scenario_evasive_maneuvering() -> pd.DataFrame:
    """
    Vessel executing sharp, irregular turns (angular rates > 20°/min),
    indicative of evasive action or awareness of surveillance.
    A naive constant-velocity tracker loses the track after each manoeuvre.
    """
    dt = 1   # 1-min pings for high manoeuvre resolution
    waypoints = [
        # (lat, lon, cog, sog, n_steps)
        (1.50, 103.40, 80,  12, 10),
        (None, None,  130, 10,  8),   # sharp right turn
        (None, None,  200,  8, 10),   # sharp right turn
        (None, None,  120, 14,  8),   # accelerate + turn
        (None, None,   30, 12, 10),   # sharp left
        (None, None,  350,  9, 10),   # sharp left
        (None, None,   80, 12,  8),   # resume near-original heading
    ]
    rows = []
    t_cur = _T0
    lat0, lon0 = waypoints[0][0], waypoints[0][1]

    for lat_wp, lon_wp, cog_wp, sog_wp, n_wp in waypoints:
        if lat_wp is not None:
            lat0, lon0 = lat_wp, lon_wp
        lw, lonw, cw, sw = _propagate(lat0, lon0, cog_deg=cog_wp, sog_kn=sog_wp,
                                       dt_min=dt, n_steps=n_wp,
                                       cog_noise=3, sog_noise=0.5)
        rows.append(pd.DataFrame({
            "mmsi": 111_008_001,
            "timestamp": [t_cur + pd.Timedelta(minutes=i*dt) for i in range(len(lw))],
            "lat": lw, "lon": lonw, "sog": sw, "cog": cw, "heading": cw,
            "sensor_type": "ais", "true_activity": "loiter",
            "vessel_type": "unknown", "nav_status": 0,
            "scenario": "evasive_maneuvering", "track_id": "A", "is_dark": False,
        }))
        t_cur += pd.Timedelta(minutes=n_wp * dt)
        lat0, lon0 = lw[-1], lonw[-1]

    return pd.concat(rows, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 9: Speed-Jump Noisy Track
# ══════════════════════════════════════════════════════════════════════════════

def scenario_speed_jump_noisy() -> pd.DataFrame:
    """
    Track with:
      - Multiple sensor modalities (AIS, EO, radar) with different accuracy
      - Outlier pings (GPS multipath / spoofed positions)
      - Random gaps (AIS blanking)
      - A genuine speed change when the vessel changes activity

    Tests noise handling and multi-source fusion.
    """
    dt = 5
    rng3 = np.random.default_rng(55)

    # Slow fishing phase
    n1 = 15
    l1, lon1, c1, s1 = _propagate(3.0, 100.0, cog_deg=90, sog_kn=3.5,
                                   dt_min=dt, n_steps=n1, cog_noise=15, sog_noise=0.8)

    # Speed jump: transit at 12 kn
    n2 = 20
    l2, lon2, c2, s2 = _propagate(l1[-1], lon1[-1], cog_deg=120, sog_kn=12,
                                   dt_min=dt, n_steps=n2, cog_noise=3, sog_noise=0.5)

    # Anchored phase at destination
    n3 = 10
    l3, lon3, c3, s3 = _propagate(l2[-1], lon2[-1], cog_deg=0, sog_kn=0.2,
                                   dt_min=dt, n_steps=n3, cog_noise=60, sog_noise=0.2)

    lats_all = np.concatenate([l1, l2, l3])
    lons_all = np.concatenate([lon1, lon2, lon3])
    cogs_all = np.concatenate([c1, c2, c3])
    sogs_all = np.concatenate([s1, s2, s3])
    acts_all = (["fishing"] * len(l1) + ["transit"] * len(l2) + ["anchored"] * len(l3))
    ns_all   = ([7] * len(l1) + [0] * len(l2) + [1] * len(l3))

    n_total = len(lats_all)
    ts_all  = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(n_total)]

    # Inject 4 outlier pings (position error 3-8 nm)
    sensors = ["ais"] * n_total
    outlier_idx = rng3.choice(n_total, 4, replace=False)
    for idx in outlier_idx:
        lats_all[idx] += rng3.uniform(0.04, 0.12) * rng3.choice([-1, 1])
        lons_all[idx] += rng3.uniform(0.04, 0.12) * rng3.choice([-1, 1])
        sensors[idx] = "eo"   # EO/satellite fix with lower accuracy

    # Random 20% gap (blank AIS rows)
    gap_mask = rng3.random(n_total) < 0.15
    for g in np.where(gap_mask)[0]:
        sensors[g] = "none"
        sogs_all[g] = np.nan
        cogs_all[g] = np.nan

    df = pd.DataFrame({
        "mmsi":          111_009_001,
        "timestamp":     ts_all,
        "lat":           lats_all,
        "lon":           lons_all,
        "sog":           sogs_all,
        "cog":           cogs_all,
        "heading":       cogs_all,
        "sensor_type":   sensors,
        "true_activity": acts_all,
        "vessel_type":   "fishing",
        "nav_status":    ns_all,
        "scenario":      "speed_jump_noisy",
        "track_id":      "A",
        "is_dark":       gap_mask,
    })
    return df


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 10: Dense Cluster
# ══════════════════════════════════════════════════════════════════════════════

def scenario_dense_cluster() -> pd.DataFrame:
    """
    12 vessels (mix of fishing and support) in a 0.5 nm radius cluster.
    Individual tracks are indistinguishable from noise in the first several
    pings.  Models must use vessel-type priors + speed profile to resolve.
    """
    dt = 2
    n  = 30
    rng4 = np.random.default_rng(123)
    dfs  = []

    centre_lat, centre_lon = 6.00, 104.50
    vtypes    = ["fishing"] * 8 + ["support_vessel"] * 2 + ["cargo"] * 1 + ["tug"] * 1
    sog_means = [3.0]*8 + [5.0]*2 + [10.0]*1 + [4.0]*1
    activities= ["fishing"]*8 + ["transit"]*3 + ["transit"]*1

    for i, (vtype, sog_m, act) in enumerate(zip(vtypes, sog_means, activities)):
        r_deg_lat = rng4.uniform(0, 0.4) / _NM_PER_DEG_LAT
        r_deg_lon = r_deg_lat / np.cos(np.radians(centre_lat))
        ang       = rng4.uniform(0, 360)
        lat0 = centre_lat + r_deg_lat * np.cos(np.radians(ang))
        lon0 = centre_lon + r_deg_lon * np.sin(np.radians(ang))
        cog0 = rng4.uniform(0, 360)

        lk, lonk, ck, sk = _propagate(lat0, lon0, cog_deg=cog0, sog_kn=sog_m,
                                       dt_min=dt, n_steps=n,
                                       cog_noise=25 if "fishing" in vtype else 5,
                                       sog_noise=0.8, rng=rng4)
        nav_s = 7 if act == "fishing" else 0
        dfs.append(_track_df(111_010_000 + i, lk, lonk, ck, sk, _T0, dt,
                             vtype=vtype, activity=act, nav_status=nav_s,
                             scenario="dense_cluster", track_id=str(i)))

    return pd.concat(dfs, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 11: Position Spoofing (Static GPS Broadcast)
# ══════════════════════════════════════════════════════════════════════════════

def scenario_position_spoofing() -> pd.DataFrame:
    """
    A cargo vessel broadcasts a static (falsified) position for 3 hours while
    actually transiting at 14 kn.  The AIS system sees a stationary vessel;
    a cross-sensor check (SAT-AIS / SAR) reveals the true position.

    Two sub-tracks share the same MMSI:
      track_id="broadcast"  — what the AIS data layer shows (frozen lat/lon)
      track_id="true"       — actual movement as revealed by satellite

    Challenges:
      - Naive tracker marks the vessel as anchored for 3h
      - Position jump when honest AIS resumes is physically impossible
      - Speed-consistency check between broadcast and satellite diverges
    """
    dt = 5    # minutes per ping

    # True continuous movement: ENE at 14 kn throughout
    n_total = 72   # 6h total
    la_true, lona_true, ca_true, sa_true = _propagate(
        1.20, 103.30, cog_deg=75, sog_kn=14,
        dt_min=dt, n_steps=n_total, cog_noise=1.0, sog_noise=0.3,
    )

    honest_pre  = 12   # first 1h honest
    spoof_start = honest_pre
    spoof_end   = honest_pre + 36   # 3h spoofed
    # honest_post = remainder

    ts_all = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(n_total + 1)]

    # ── Broadcast track ───────────────────────────────────────────────────────
    # Pre-spoof: honest pings
    broadcast_lats = list(la_true[:honest_pre + 1])
    broadcast_lons = list(lona_true[:honest_pre + 1])
    # Spoof phase: GPS frozen at the position when spoofing began
    frozen_lat = la_true[spoof_start]
    frozen_lon = lona_true[spoof_start]
    for _ in range(spoof_end - spoof_start):
        broadcast_lats.append(frozen_lat + _RNG.normal(0, 0.00005))   # tiny jitter
        broadcast_lons.append(frozen_lon + _RNG.normal(0, 0.00005))
    # Post-spoof: honest pings resume (sudden jump)
    broadcast_lats.extend(la_true[spoof_end + 1:])
    broadcast_lons.extend(lona_true[spoof_end + 1:])

    n_b = min(len(broadcast_lats), len(ts_all))
    broadcast_sogs = (
        list(sa_true[:honest_pre + 1]) +
        [0.1] * (spoof_end - spoof_start) +   # reports near-zero speed
        list(sa_true[spoof_end + 1:])
    )[:n_b]
    broadcast_cogs = (
        list(ca_true[:honest_pre + 1]) +
        [ca_true[spoof_start]] * (spoof_end - spoof_start) +
        list(ca_true[spoof_end + 1:])
    )[:n_b]

    df_broadcast = pd.DataFrame({
        "mmsi":          111_011_001,
        "timestamp":     ts_all[:n_b],
        "lat":           broadcast_lats[:n_b],
        "lon":           broadcast_lons[:n_b],
        "sog":           broadcast_sogs,
        "cog":           broadcast_cogs,
        "heading":       broadcast_cogs,
        "sensor_type":   "ais",
        "true_activity": (["transit"] * (honest_pre + 1) +
                          ["spoofed"] * (spoof_end - spoof_start) +
                          ["transit"] * max(0, n_b - spoof_end - 1)),
        "vessel_type":   "cargo",
        "nav_status":    ([0] * (honest_pre + 1) +
                          [1] * (spoof_end - spoof_start) +   # reports anchored
                          [0] * max(0, n_b - spoof_end - 1)),
        "scenario":      "position_spoofing",
        "track_id":      "broadcast",
        "is_dark":       False,
    })

    # ── True track (SAT-AIS / SAR revelation) ────────────────────────────────
    n_t = n_total + 1
    df_true = pd.DataFrame({
        "mmsi":          111_011_001,
        "timestamp":     ts_all[:n_t],
        "lat":           la_true,
        "lon":           lona_true,
        "sog":           sa_true,
        "cog":           ca_true,
        "heading":       ca_true,
        "sensor_type":   (["ais"] * (honest_pre + 1) +
                          ["satellite_ais"] * (spoof_end - spoof_start) +
                          ["ais"] * max(0, n_t - spoof_end - 1)),
        "true_activity": "transit",
        "vessel_type":   "cargo",
        "nav_status":    0,
        "scenario":      "position_spoofing",
        "track_id":      "true",
        "is_dark":       False,
    })

    return pd.concat([df_broadcast, df_true], ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 12: Track Fragmentation
# ══════════════════════════════════════════════════════════════════════════════

def scenario_track_fragmentation() -> pd.DataFrame:
    """
    A single fishing vessel transmits in irregular, short bursts separated by
    20–45 minute AIS gaps (poor equipment, deliberate blanking, or obstruction).

    The same MMSI appears as 6 disconnected fragments.  A tracker must decide:
      (a) stitch them into one track using dead-reckoning plausibility, or
      (b) treat each burst as a separate object.

    Position continuity across gaps is consistent with one vessel at ~4 kn,
    but each fragment alone is too short for confident activity classification.
    """
    dt = 2   # 2-min pings within each burst
    MMSI = 111_012_001

    # Simulate the full underlying track at fine resolution
    n_full = 200
    la, lona, ca, sa = _propagate(
        3.50, 102.00, cog_deg=110, sog_kn=4.0,
        dt_min=dt, n_steps=n_full, cog_noise=18, sog_noise=0.6,
    )
    ts_full = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(n_full + 1)]

    # Define bursts as (start_ping, n_pings); gaps in between are dark
    bursts = [
        (0,   5),    # burst 1: 5 pings
        (20,  4),    # gap ~40 min, burst 2: 4 pings
        (37,  6),    # gap ~34 min, burst 3: 6 pings
        (60,  3),    # gap ~46 min, burst 4: 3 pings
        (85,  7),    # gap ~50 min, burst 5: 7 pings
        (115, 5),    # gap ~60 min, burst 6: 5 pings
    ]

    rows = []
    for burst_start, burst_len in bursts:
        end = min(burst_start + burst_len, len(la))
        for j in range(burst_start, end):
            rows.append({
                "mmsi":          MMSI,
                "timestamp":     ts_full[j],
                "lat":           la[j],
                "lon":           lona[j],
                "sog":           sa[j],
                "cog":           ca[j],
                "heading":       ca[j],
                "sensor_type":   "ais",
                "true_activity": "fishing",
                "vessel_type":   "fishing",
                "nav_status":    7,
                "scenario":      "track_fragmentation",
                "track_id":      f"burst_{bursts.index((burst_start, burst_len)) + 1}",
                "is_dark":       False,
            })

    # Add gap-period rows (dark, no sensor) to make gaps visible to the tracker
    burst_ends  = {b[0] + b[1] for b in bursts}
    burst_starts = {b[0] for b in bursts}
    in_burst = set()
    for bs, bl in bursts:
        for k in range(bs, bs + bl):
            in_burst.add(k)

    for j in range(n_full + 1):
        if j not in in_burst:
            rows.append({
                "mmsi":          MMSI,
                "timestamp":     ts_full[j],
                "lat":           la[j],
                "lon":           lona[j],
                "sog":           np.nan,
                "cog":           np.nan,
                "heading":       np.nan,
                "sensor_type":   "none",
                "true_activity": "fishing",
                "vessel_type":   "fishing",
                "nav_status":    np.nan,
                "scenario":      "track_fragmentation",
                "track_id":      "gap",
                "is_dark":       True,
            })

    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 13: Bunkering Rendezvous
# ══════════════════════════════════════════════════════════════════════════════

def scenario_bunkering_rendezvous() -> pd.DataFrame:
    """
    A bunker barge (small tanker) meets a Panamax cargo vessel in a port
    approach anchorage.  Duration of the fuel transfer is 90 min, after which
    the cargo departs at speed and the barge returns toward port.

    Background clutter: 3 transiting vessels in the same anchorage area.

    Challenges:
      - Barge and cargo are both near-stationary for 90 min → confused with
        anchored vessels or loiterers
      - Proximity of the two stationary vessels triggers a false STS alert
      - High traffic density near port approach complicates track assignment
    """
    dt = 3   # 3-min pings

    anch_lat, anch_lon = 1.10, 103.55   # Singapore Strait approach

    dfs = []

    # ── Cargo vessel ──────────────────────────────────────────────────────────
    n_approach = 20   # 60 min inbound
    n_bunker   = 30   # 90 min bunkering
    n_depart   = 25   # 75 min outbound

    lc_ap, lonc_ap, cc_ap, sc_ap = _propagate(
        anch_lat - 0.30, anch_lon - 0.20, cog_deg=45, sog_kn=10,
        dt_min=dt, n_steps=n_approach, cog_noise=1)
    lc_bk, lonc_bk, cc_bk, sc_bk = _propagate(
        lc_ap[-1], lonc_ap[-1], cog_deg=90, sog_kn=0.2,
        dt_min=dt, n_steps=n_bunker, cog_noise=40, sog_noise=0.1)
    lc_dp, lonc_dp, cc_dp, sc_dp = _propagate(
        lc_bk[-1], lonc_bk[-1], cog_deg=90, sog_kn=12,
        dt_min=dt, n_steps=n_depart, cog_noise=1)

    def _concat_track(mmsi, segs, acts, vtype, tid):
        lats = np.concatenate([s[0] for s in segs])
        lons = np.concatenate([s[1] for s in segs])
        cogs = np.concatenate([s[2] for s in segs])
        sogs = np.concatenate([s[3] for s in segs])
        activities = []
        for act, seg in zip(acts, segs):
            activities.extend([act] * len(seg[0]))
        n = len(lats)
        ts = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(n)]
        return pd.DataFrame({
            "mmsi": mmsi, "timestamp": ts, "lat": lats, "lon": lons,
            "sog": sogs, "cog": cogs, "heading": cogs,
            "sensor_type": "ais",
            "true_activity": activities[:n],
            "vessel_type": vtype, "nav_status": 0,
            "scenario": "bunkering_rendezvous",
            "track_id": tid, "is_dark": False,
        })

    cargo_segs = [
        (lc_ap, lonc_ap, cc_ap, sc_ap),
        (lc_bk, lonc_bk, cc_bk, sc_bk),
        (lc_dp, lonc_dp, cc_dp, sc_dp),
    ]
    dfs.append(_concat_track(111_013_001, cargo_segs,
                              ["transit", "bunkering", "transit"], "cargo", "cargo"))

    # ── Bunker barge ──────────────────────────────────────────────────────────
    n_b_approach = 15
    n_b_bunker   = 30
    n_b_return   = 15

    lb_ap, lonb_ap, cb_ap, sb_ap = _propagate(
        anch_lat + 0.10, anch_lon + 0.05, cog_deg=220, sog_kn=7,
        dt_min=dt, n_steps=n_b_approach, cog_noise=2)
    lb_bk, lonb_bk, cb_bk, sb_bk = _propagate(
        lb_ap[-1], lonb_ap[-1], cog_deg=270, sog_kn=0.3,
        dt_min=dt, n_steps=n_b_bunker, cog_noise=30, sog_noise=0.15)
    lb_rt, lonb_rt, cb_rt, sb_rt = _propagate(
        lb_bk[-1], lonb_bk[-1], cog_deg=40, sog_kn=8,
        dt_min=dt, n_steps=n_b_return, cog_noise=2)

    barge_segs = [
        (lb_ap, lonb_ap, cb_ap, sb_ap),
        (lb_bk, lonb_bk, cb_bk, sb_bk),
        (lb_rt, lonb_rt, cb_rt, sb_rt),
    ]
    dfs.append(_concat_track(111_013_002, barge_segs,
                              ["transit", "bunkering", "transit"],
                              "tanker", "barge"))

    # ── Background traffic (3 transiting vessels) ────────────────────────────
    bg_starts = [
        (anch_lat - 0.5, anch_lon - 0.8, 80,  14, "cargo"),
        (anch_lat + 0.3, anch_lon - 0.6, 95,  12, "tanker"),
        (anch_lat - 0.2, anch_lon - 0.7, 75,  16, "cargo"),
    ]
    for k, (la0, lo0, cog0, sog0, vt) in enumerate(bg_starts):
        n_bg = 50
        lbg, lonbg, cbg, sbg = _propagate(
            la0, lo0, cog_deg=cog0, sog_kn=sog0,
            dt_min=dt, n_steps=n_bg, cog_noise=0.5)
        ts_bg = [_T0 + pd.Timedelta(minutes=i * dt) for i in range(n_bg + 1)]
        dfs.append(pd.DataFrame({
            "mmsi": 111_013_100 + k, "timestamp": ts_bg,
            "lat": lbg, "lon": lonbg, "sog": sbg, "cog": cbg, "heading": cbg,
            "sensor_type": "ais", "true_activity": "transit",
            "vessel_type": vt, "nav_status": 0,
            "scenario": "bunkering_rendezvous",
            "track_id": f"bg_{k}", "is_dark": False,
        }))

    return pd.concat(dfs, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Master generator
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_LABELS = {
    "crossing_tracks":         "Crossing Tracks",
    "near_parallel":           "Near-Parallel Tracks (<0.3 nm separation)",
    "sts_rendezvous":          "STS Rendezvous (Converge → Dwell → Depart)",
    "dark_reacquisition":      "Dark Period + Dead-Reckoning Reacquisition",
    "trawling_pattern":        "Trawling S-Curve + Transit Pattern",
    "coordinated_fleet":       "Coordinated Purse-Seine Fleet Encirclement",
    "mmsi_clone":              "MMSI Cloning / Identity Spoofing",
    "evasive_maneuvering":     "Evasive Maneuvering (High Angular Rate)",
    "speed_jump_noisy":        "Multi-Sensor Noisy Track + Speed Jump",
    "dense_cluster":           "Dense Cluster (12 vessels in 0.5 nm)",
    "position_spoofing":       "Static GPS Broadcast / Position Spoofing",
    "track_fragmentation":     "Track Fragmentation (Burst AIS, 6 Gaps)",
    "bunkering_rendezvous":    "Bunkering Rendezvous (Port Approach Anchorage)",
}

_GENERATORS = {
    "crossing_tracks":      scenario_crossing_tracks,
    "near_parallel":        scenario_near_parallel,
    "sts_rendezvous":       scenario_sts_rendezvous,
    "dark_reacquisition":   scenario_dark_reacquisition,
    "trawling_pattern":     scenario_trawling_pattern,
    "coordinated_fleet":    scenario_coordinated_fleet,
    "mmsi_clone":           scenario_mmsi_clone,
    "evasive_maneuvering":  scenario_evasive_maneuvering,
    "speed_jump_noisy":     scenario_speed_jump_noisy,
    "dense_cluster":        scenario_dense_cluster,
    "position_spoofing":    scenario_position_spoofing,
    "track_fragmentation":  scenario_track_fragmentation,
    "bunkering_rendezvous": scenario_bunkering_rendezvous,
}


def generate_all_scenarios() -> Dict[str, pd.DataFrame]:
    """Generate all 10 benchmark scenarios. Returns dict keyed by scenario name."""
    return {name: fn() for name, fn in _GENERATORS.items()}


def generate_scenario(name: str) -> pd.DataFrame:
    """Generate a single named scenario."""
    if name not in _GENERATORS:
        raise ValueError(f"Unknown scenario '{name}'. Options: {list(_GENERATORS)}")
    return _GENERATORS[name]()


# ══════════════════════════════════════════════════════════════════════════════
# CSV export — replay-ready format
# ══════════════════════════════════════════════════════════════════════════════

def export_scenarios_to_csv(
    output_dir: str = "outputs/tracking_scenarios",
    scenarios: Optional[Dict[str, pd.DataFrame]] = None,
) -> str:
    """
    Export all benchmark scenarios to CSV files ready for sequential playback.

    Each scenario → <output_dir>/<scenario_name>.csv, rows sorted by timestamp
    so a replay service can stream them in order at any desired rate.

    A manifest.json is written alongside with per-scenario metadata (ping count,
    time range, vessel types, activities, sensor modes) to help the partner test
    suite discover and validate the files without parsing CSVs.

    Returns the path to manifest.json.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if scenarios is None:
        scenarios = generate_all_scenarios()

    manifest: dict = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "format_version": "1.1",
        "column_schema": {
            "mmsi":          "int — vessel MMSI (may repeat for clones/spoofing)",
            "timestamp":     "ISO 8601 UTC — sort this column for IRL playback",
            "lat":           "float — decimal degrees WGS-84",
            "lon":           "float — decimal degrees WGS-84",
            "sog":           "float — speed over ground, knots (NaN in dark gaps)",
            "cog":           "float — course over ground, degrees (NaN in dark gaps)",
            "heading":       "float — true heading degrees (NaN in dark gaps)",
            "sensor_type":   "str — ais | satellite_ais | radar | eo | none",
            "true_activity": "str — ground-truth activity label",
            "vessel_type":   "str — vessel type key",
            "nav_status":    "int — AIS navigation status code",
            "scenario":      "str — scenario name key",
            "track_id":      "str — per-scenario track identifier",
            "is_dark":       "bool — True for AIS gap / dark period rows",
        },
        "replay_note": (
            "Rows are sorted by timestamp. "
            "A replay service can iterate rows sequentially, sleeping "
            "(row[i+1].timestamp - row[i].timestamp) between emissions. "
            "is_dark=True rows carry position via dead-reckoning for visualisation "
            "but have NaN sog/cog; filter them out if feeding a live classifier."
        ),
        "scenarios": {},
    }

    for name, df in scenarios.items():
        df_out = df.copy()
        # Normalise timestamp to ISO strings for portability
        if pd.api.types.is_datetime64_any_dtype(df_out["timestamp"]):
            df_out["timestamp"] = df_out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        df_out = df_out.sort_values("timestamp").reset_index(drop=True)

        csv_path = out / f"{name}.csv"
        df_out.to_csv(csv_path, index=False)

        # Metadata for manifest
        ts_series = pd.to_datetime(df_out["timestamp"])
        duration_min = float(
            (ts_series.max() - ts_series.min()).total_seconds() / 60
        )
        manifest["scenarios"][name] = {
            "label":          SCENARIO_LABELS.get(name, name),
            "file":           f"{name}.csv",
            "n_pings":        int(len(df_out)),
            "n_pings_live":   int((~df_out["is_dark"]).sum()),
            "n_tracks":       int(df_out["track_id"].nunique()),
            "n_vessels":      int(df_out["mmsi"].nunique()),
            "t_start":        ts_series.min().isoformat(),
            "t_end":          ts_series.max().isoformat(),
            "duration_minutes": round(duration_min, 1),
            "vessel_types":   sorted(df_out["vessel_type"].dropna().unique().tolist()),
            "activities":     sorted(df_out["true_activity"].dropna().unique().tolist()),
            "sensor_types":   sorted(df_out["sensor_type"].dropna().unique().tolist()),
            "has_dark_pings": bool(df_out["is_dark"].any()),
        }

    manifest_path = out / "manifest.json"
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"Exported {len(scenarios)} scenarios → {out}/")
    print(f"Manifest: {manifest_path}")
    return str(manifest_path)
