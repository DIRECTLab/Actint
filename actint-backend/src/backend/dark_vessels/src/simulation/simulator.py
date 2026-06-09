"""
AIS vessel track simulator.

Generates realistic synthetic AIS tracks for:
  - Fishing vessels (trawlers, longliners, purse seiners)
  - Cargo / container ships
  - Tankers (crude, LNG, product)
  - Bulk carriers
  - Naval / patrol
  - Dark vessels (AIS-off stretches + spoofing)
  - STS (ship-to-ship transfer) rendezvous pairs

Each track is a DataFrame with columns matching the AIS standard:
  mmsi, vessel_type, timestamp, lat, lon, sog, cog, heading,
  nav_status, length, width, draught, name, flag,
  ais_on (bool – False = dark period)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

RNG = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Vessel templates
# ---------------------------------------------------------------------------

VESSEL_TEMPLATES = {
    "trawler": {
        "type_code": 30,  # AIS type: fishing
        "length_range": (20, 80),
        "width_range": (5, 15),
        "draught_range": (3, 6),
        "transit_sog": (8, 14),     # knots while transiting to grounds
        "fishing_sog": (2, 5),      # knots while trawling
        "typical_dark_prob": 0.10,  # 10% chance of going dark per voyage
    },
    "longliner": {
        "type_code": 30,
        "length_range": (25, 60),
        "width_range": (6, 12),
        "draught_range": (2, 5),
        "transit_sog": (10, 14),
        "fishing_sog": (0.5, 3),
        "typical_dark_prob": 0.15,
    },
    "purse_seiner": {
        "type_code": 30,
        "length_range": (40, 100),
        "width_range": (8, 18),
        "draught_range": (4, 7),
        "transit_sog": (12, 16),
        "fishing_sog": (1, 6),      # encircling behaviour
        "typical_dark_prob": 0.12,
    },
    "cargo": {
        "type_code": 70,
        "length_range": (100, 300),
        "width_range": (18, 45),
        "draught_range": (6, 14),
        "transit_sog": (12, 22),
        "fishing_sog": (12, 22),    # no fishing mode
        "typical_dark_prob": 0.02,
    },
    "tanker": {
        "type_code": 80,
        "length_range": (150, 330),
        "width_range": (25, 60),
        "draught_range": (10, 22),
        "transit_sog": (10, 16),
        "fishing_sog": (10, 16),
        "typical_dark_prob": 0.05,
    },
    "bulk_carrier": {
        "type_code": 71,
        "length_range": (100, 290),
        "width_range": (20, 48),
        "draught_range": (8, 18),
        "transit_sog": (10, 15),
        "fishing_sog": (10, 15),
        "typical_dark_prob": 0.03,
    },
    "naval": {
        "type_code": 35,
        "length_range": (50, 200),
        "width_range": (8, 22),
        "draught_range": (4, 8),
        "transit_sog": (15, 30),
        "fishing_sog": (3, 8),      # patrol speed
        "typical_dark_prob": 0.40,  # navies go dark often
    },
    "support_vessel": {  # PSV / AHTS for offshore
        "type_code": 31,
        "length_range": (50, 100),
        "width_range": (14, 22),
        "draught_range": (4, 7),
        "transit_sog": (10, 16),
        "fishing_sog": (0, 2),      # DP / on-station
        "typical_dark_prob": 0.04,
    },
    "bunker_barge": {           # small fuel tanker
        "type_code": 80,
        "length_range": (30, 80),
        "width_range": (8, 15),
        "draught_range": (2, 5),
        "transit_sog": (6, 10),
        "fishing_sog": (0, 0.5),    # nearly stationary during bunkering
        "typical_dark_prob": 0.02,
    },
    "reefer_carrier": {         # refrigerated cargo for transshipment
        "type_code": 70,
        "length_range": (100, 180),
        "width_range": (20, 30),
        "draught_range": (6, 10),
        "transit_sog": (14, 18),
        "fishing_sog": (0.5, 2.0),  # slow drift during transshipment
        "typical_dark_prob": 0.08,
    },
    "survey_vessel": {          # seismic / hydrographic survey
        "type_code": 31,
        "length_range": (60, 120),
        "width_range": (12, 20),
        "draught_range": (4, 7),
        "transit_sog": (10, 15),
        "fishing_sog": (3, 5),      # slow systematic survey lines
        "typical_dark_prob": 0.01,
    },
    "patrol_vessel": {          # coast guard / law enforcement
        "type_code": 55,
        "length_range": (20, 60),
        "width_range": (5, 12),
        "draught_range": (2, 4),
        "transit_sog": (15, 25),
        "fishing_sog": (8, 12),     # patrol speed
        "typical_dark_prob": 0.15,
    },
    "dredger": {                # port / channel dredging
        "type_code": 33,
        "length_range": (60, 120),
        "width_range": (14, 25),
        "draught_range": (4, 8),
        "transit_sog": (8, 12),
        "fishing_sog": (1, 2.5),    # dredging work speed
        "typical_dark_prob": 0.01,
    },
}

# Nav status codes (AIS standard)
NAV_STATUS = {
    "underway_engine": 0,
    "anchored": 1,
    "not_under_command": 2,
    "restricted_maneuverability": 3,
    "moored": 5,
    "aground": 6,
    "fishing": 7,
    "underway_sailing": 8,
}

FLAGS = {
    "brazil_eez": ["BR", "BR", "BR", "CN", "KR", "TW", "ES", "PT", "VU", "PA"],
    "philippines_eez": ["PH", "PH", "CN", "CN", "TW", "VN", "ID", "PA", "SG", "MH"],
    "strait_of_malacca": ["SG", "MY", "CN", "PH", "JP", "KR", "LR", "PA", "MH"],
    "gulf_of_guinea": ["NG", "GH", "CM", "GA", "CN", "KR", "SL", "PA", "LR"],
}


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _nm_to_deg_lat(nm: float) -> float:
    return nm / 60.0


def _nm_to_deg_lon(nm: float, lat: float) -> float:
    return nm / (60.0 * np.cos(np.radians(lat)))


def _step(lat, lon, sog_kn, cog_deg, dt_sec):
    """Advance a position by sog/cog over dt seconds."""
    dist_nm = sog_kn * (dt_sec / 3600.0)
    dlat = _nm_to_deg_lat(dist_nm * np.cos(np.radians(cog_deg)))
    dlon = _nm_to_deg_lon(dist_nm * np.sin(np.radians(cog_deg)), lat)
    return lat + dlat, lon + dlon


def _random_cog_change(current_cog, sigma=5):
    """Small random heading perturbation."""
    return (current_cog + RNG.normal(0, sigma)) % 360


# ---------------------------------------------------------------------------
# Core track builder
# ---------------------------------------------------------------------------

def _build_track(
    mmsi: int,
    vessel_key: str,
    start_lat: float,
    start_lon: float,
    start_time: datetime,
    duration_hours: float,
    activity_sequence: list,  # list of (phase, hours) tuples
    dark_segments: list,      # list of (start_frac, end_frac) – fraction of total time
    flag: str,
    name: str,
    dt_sec: int = 300,         # AIS ping interval (5 min default)
) -> pd.DataFrame:

    tmpl = VESSEL_TEMPLATES[vessel_key]
    length = RNG.integers(*tmpl["length_range"])
    width = RNG.integers(*tmpl["width_range"])
    draught = round(RNG.uniform(*tmpl["draught_range"]), 1)

    total_sec = duration_hours * 3600
    n_steps = int(total_sec / dt_sec) + 1

    records = []
    lat, lon = start_lat, start_lon
    cog = RNG.uniform(0, 360)
    t = start_time

    # Build phase schedule
    phase_schedule = []
    elapsed = 0.0
    for phase, hrs in activity_sequence:
        phase_schedule.append((elapsed, elapsed + hrs, phase))
        elapsed += hrs

    def get_phase(frac):
        h = frac * duration_hours
        for s, e, p in phase_schedule:
            if s <= h < e:
                return p
        return phase_schedule[-1][2]

    def is_dark(frac):
        for ds, de in dark_segments:
            if ds <= frac <= de:
                return True
        return False

    sog = RNG.uniform(*tmpl["transit_sog"])

    for i in range(n_steps):
        frac = i / max(n_steps - 1, 1)
        phase = get_phase(frac)
        dark = is_dark(frac)

        # During dark periods skip this ping (realistic AIS gap)
        if dark:
            lat, lon = _step(lat, lon, sog, cog, dt_sec)
            t += timedelta(seconds=dt_sec)
            continue

        # Speed based on phase
        if phase == "fishing":
            target_sog = RNG.uniform(*tmpl["fishing_sog"])
        elif phase == "anchored":
            target_sog = 0.0
        elif phase == "loiter":
            target_sog = RNG.uniform(0.5, 3.0)
        elif phase == "sts":
            target_sog = RNG.uniform(0.0, 2.0)
        elif phase == "transshipment":
            target_sog = RNG.uniform(0.3, 1.5)
        elif phase == "bunkering":
            target_sog = RNG.uniform(0.0, 0.5)
        elif phase == "dredging":
            target_sog = RNG.uniform(1.0, 2.5)
        elif phase == "survey":
            target_sog = RNG.uniform(3.0, 5.0)
        elif phase == "patrol_sweep":
            target_sog = RNG.uniform(8.0, 12.0)
        else:
            target_sog = RNG.uniform(*tmpl["transit_sog"])

        # Smooth speed change
        sog = sog * 0.85 + target_sog * 0.15 + RNG.normal(0, 0.3)
        sog = max(0.0, sog)

        # Heading
        if phase in ("fishing", "loiter"):
            cog = _random_cog_change(cog, sigma=25)
        elif phase == "anchored":
            cog = _random_cog_change(cog, sigma=2)
        elif phase == "transshipment":
            cog = _random_cog_change(cog, sigma=20)   # drifting alongside
        elif phase == "bunkering":
            cog = _random_cog_change(cog, sigma=3)    # moored alongside
        elif phase == "dredging":
            cog = _random_cog_change(cog, sigma=5)    # following channel
        elif phase == "survey":
            cog = _random_cog_change(cog, sigma=2)    # tight survey line
        elif phase == "patrol_sweep":
            cog = _random_cog_change(cog, sigma=8)
        else:
            cog = _random_cog_change(cog, sigma=4)

        nav_status = {
            "fishing":       NAV_STATUS["fishing"],
            "transit":       NAV_STATUS["underway_engine"],
            "anchored":      NAV_STATUS["anchored"],
            "loiter":        NAV_STATUS["underway_engine"],
            "sts":           NAV_STATUS["restricted_maneuverability"],
            "port":          NAV_STATUS["moored"],
            "transshipment": NAV_STATUS["restricted_maneuverability"],
            "bunkering":     NAV_STATUS["restricted_maneuverability"],
            "dredging":      NAV_STATUS["restricted_maneuverability"],
            "survey":        NAV_STATUS["restricted_maneuverability"],
            "patrol_sweep":  NAV_STATUS["underway_engine"],
        }.get(phase, 0)

        # AIS sensor noise (realistic ±0.1 kn on SOG, ±1° on COG)
        reported_sog = max(0.0, sog + RNG.normal(0, 0.15))
        reported_cog = (cog + RNG.normal(0, 1.0)) % 360

        records.append({
            "mmsi": mmsi,
            "vessel_type_key": vessel_key,
            "vessel_type_code": tmpl["type_code"],
            "timestamp": t,
            "lat": round(lat + RNG.normal(0, 0.0002), 5),
            "lon": round(lon + RNG.normal(0, 0.0002), 5),
            "sog": round(reported_sog, 1),
            "cog": round(reported_cog, 1),
            "heading": round(reported_cog + RNG.normal(0, 2), 1) % 360,
            "nav_status": nav_status,
            "length": int(length),
            "width": int(width),
            "draught": draught,
            "name": name,
            "flag": flag,
            "ais_on": True,
            "true_activity": phase,
            "had_dark_period": len(dark_segments) > 0,
        })
        
        lat, lon = _step(lat, lon, sog, cog, dt_sec)
        t += timedelta(seconds=dt_sec)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def simulate_fishing_fleet(region_key: str, n_vessels: int = 15,
                            duration_hours: float = 72.0) -> pd.DataFrame:
    """Simulate a fishing fleet operating in a region."""
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    flags = FLAGS.get(region_key, ["XX"])
    vessel_types = ["trawler", "longliner", "purse_seiner"]
    start_time = datetime(2024, 6, 1, 0, 0, 0)

    tracks = []
    for i in range(n_vessels):
        mmsi = 700_000_000 + i + (hash(region_key) % 100_000)
        vtype = RNG.choice(vessel_types)
        tmpl = VESSEL_TEMPLATES[vtype]

        # Start near a fishing ground or random point in bbox
        if "fishing_grounds" in region and RNG.random() > 0.3:
            g = RNG.choice(region["fishing_grounds"])
            r_nm = g.get("radius_nm", 80)
            r_deg = r_nm / 60.0
            start_lat = g["lat"] + RNG.uniform(-r_deg, r_deg)
            start_lon = g["lon"] + RNG.uniform(-r_deg, r_deg)
        else:
            start_lat = RNG.uniform(bbox[1], bbox[3])
            start_lon = RNG.uniform(bbox[0], bbox[2])

        flag = RNG.choice(flags)

        # Activity: transit out → fish → transit back (maybe multiple fishing bouts)
        transit_h = RNG.uniform(4, 12)
        fish1_h   = RNG.uniform(8, 24)
        transit2_h = RNG.uniform(2, 6)
        fish2_h   = RNG.uniform(6, 18)
        transit3_h = RNG.uniform(4, 10)
        sequence = [
            ("transit", transit_h),
            ("fishing", fish1_h),
            ("transit", transit2_h),
            ("fishing", fish2_h),
            ("transit", transit3_h),
        ]

        # Dark segments: some vessels go dark while fishing
        dark_segs = []
        if RNG.random() < tmpl["typical_dark_prob"]:
            # Go dark during peak fishing
            f1_start = transit_h / duration_hours
            f1_end   = (transit_h + fish1_h * 0.8) / duration_hours
            dark_segs.append((f1_start, f1_end))

        name = f"VESSEL_{region_key[:3].upper()}_{i:03d}"
        track = _build_track(
            mmsi=mmsi, vessel_key=vtype,
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time + timedelta(hours=RNG.uniform(0, 12)),
            duration_hours=duration_hours,
            activity_sequence=sequence,
            dark_segments=dark_segs,
            flag=flag, name=name,
        )
        tracks.append(track)

    return pd.concat(tracks, ignore_index=True)


def simulate_cargo_traffic(region_key: str, n_vessels: int = 10,
                           duration_hours: float = 48.0) -> pd.DataFrame:
    """Simulate cargo/tanker transit through a region."""
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    flags = FLAGS.get(region_key, ["XX"])
    vessel_types = ["cargo", "tanker", "bulk_carrier"]
    start_time = datetime(2024, 6, 1, 6, 0, 0)

    tracks = []
    for i in range(n_vessels):
        mmsi = 500_000_000 + i + (hash(region_key) % 100_000)
        vtype = RNG.choice(vessel_types)

        # Enter from one side, exit the other
        lat_span = bbox[3] - bbox[1]
        lon_span = bbox[2] - bbox[0]
        enter_side = RNG.choice(["W", "E", "N", "S"])
        if enter_side == "W":
            start_lat = RNG.uniform(bbox[1] + lat_span * 0.2, bbox[3] - lat_span * 0.2)
            start_lon = bbox[0]
        elif enter_side == "E":
            start_lat = RNG.uniform(bbox[1] + lat_span * 0.2, bbox[3] - lat_span * 0.2)
            start_lon = bbox[2]
        elif enter_side == "N":
            start_lat = bbox[3]
            start_lon = RNG.uniform(bbox[0] + lon_span * 0.2, bbox[2] - lon_span * 0.2)
        else:
            start_lat = bbox[1]
            start_lon = RNG.uniform(bbox[0] + lon_span * 0.2, bbox[2] - lon_span * 0.2)

        flag = RNG.choice(flags)
        sequence = [("transit", duration_hours)]
        dark_segs = []
        if RNG.random() < VESSEL_TEMPLATES[vtype]["typical_dark_prob"]:
            # Suspicious: go dark in middle of transit
            dark_segs.append((0.35, 0.65))

        name = f"MV_{region_key[:3].upper()}_CARGO_{i:03d}"
        track = _build_track(
            mmsi=mmsi, vessel_key=vtype,
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time + timedelta(hours=RNG.uniform(0, 6)),
            duration_hours=duration_hours,
            activity_sequence=sequence,
            dark_segments=dark_segs,
            flag=flag, name=name,
        )
        tracks.append(track)

    return pd.concat(tracks, ignore_index=True)


def simulate_sts_event(region_key: str, event_idx: int = 0) -> pd.DataFrame:
    """Simulate a ship-to-ship transfer (sanctions evasion / oil transfer)."""
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    start_time = datetime(2024, 6, 3, 2, 0, 0) + timedelta(hours=event_idx * 18)

    # Rendezvous location – mid-region, away from ports
    rv_lat = (bbox[1] + bbox[3]) / 2 + RNG.uniform(-2, 2)
    rv_lon = (bbox[0] + bbox[2]) / 2 + RNG.uniform(-2, 2)

    tracks = []
    for i, vtype in enumerate(["tanker", "tanker"]):
        mmsi = 900_000_000 + event_idx * 10 + i + (hash(region_key) % 10_000)
        flag = "PA" if i == 0 else "VU"  # flags of convenience
        # No dark period — STS phase now always visible for training labels
        sequence = [
            ("transit", 8),
            ("sts", 6),
            ("transit", 10),
        ]

        name = f"STS_TANKER_{event_idx}_{i+1}"
        track = _build_track(
            mmsi=mmsi, vessel_key=vtype,
            start_lat=rv_lat + RNG.uniform(-1, 1),
            start_lon=rv_lon + RNG.uniform(-1, 1),
            start_time=start_time,
            duration_hours=24,
            activity_sequence=sequence,
            dark_segments=[],    # keep STS segments visible
            flag=flag, name=name,
        )
        tracks.append(track)

    return pd.concat(tracks, ignore_index=True)


def simulate_loiterers(region_key: str, n_vessels: int = 4) -> pd.DataFrame:
    """Simulate vessels loitering (possible waiting for instructions / smuggling)."""
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    start_time = datetime(2024, 6, 2, 18, 0, 0)
    tracks = []
    for i in range(n_vessels):
        mmsi  = 800_000_000 + i + (hash(region_key) % 10_000)
        # Anchor-ish loiter: far from ports
        start_lat = RNG.uniform(bbox[1] + 1, bbox[3] - 1)
        start_lon = RNG.uniform(bbox[0] + 1, bbox[2] - 1)
        flag = RNG.choice(FLAGS.get(region_key, ["XX"]))
        sequence = [
            ("transit", 6),
            ("loiter",  18),
            ("anchored", 4),
            ("loiter",  12),
            ("transit",  6),
        ]
        name = f"LOITER_{region_key[:3].upper()}_{i:02d}"
        track = _build_track(
            mmsi=mmsi, vessel_key="cargo",
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time,
            duration_hours=46,
            activity_sequence=sequence,
            dark_segments=[],
            flag=flag, name=name,
        )
        tracks.append(track)
    return pd.concat(tracks, ignore_index=True)


def simulate_anchored_fleet(region_key: str, n_vessels: int = 5) -> pd.DataFrame:
    """Simulate vessels anchored at sea (offshore, waiting for berth, etc.)."""
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox   = region["bbox"]
    ports  = region.get("primary_ports", [])
    start_time = datetime(2024, 6, 1, 12, 0, 0)
    tracks = []
    for i in range(n_vessels):
        mmsi = 600_000_000 + i + (hash(region_key) % 10_000)
        if ports:
            p = RNG.choice(ports)
            start_lat = p["lat"] + RNG.uniform(-0.5, 0.5)
            start_lon = p["lon"] + RNG.uniform(-0.5, 0.5)
        else:
            start_lat = RNG.uniform(bbox[1], bbox[3])
            start_lon = RNG.uniform(bbox[0], bbox[2])

        flag = RNG.choice(["BR", "CN", "PA", "LR", "MH"])
        sequence = [("anchored", 24)]
        name = f"ANCHORED_{region_key[:3].upper()}_{i:02d}"
        vtype = RNG.choice(["cargo", "tanker", "bulk_carrier"])
        track = _build_track(
            mmsi=mmsi, vessel_key=vtype,
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time,
            duration_hours=24,
            activity_sequence=sequence,
            dark_segments=[],
            flag=flag, name=name,
        )
        tracks.append(track)
    return pd.concat(tracks, ignore_index=True)


def simulate_transshipment(region_key: str, event_idx: int = 0) -> pd.DataFrame:
    """
    Simulate a fishing-to-reefer transshipment at sea.

    A reefer carrier rendezvous with a fishing vessel on the fishing grounds;
    both go slow / nearly stationary during the transfer, then separate.
    This is a key IUU indicator (catch transferred without port inspection).
    """
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox   = region["bbox"]
    start_time = datetime(2024, 6, 4, 8, 0, 0)

    grounds = region.get("fishing_grounds", [])
    if grounds:
        g = RNG.choice(grounds)
        rv_lat = g["lat"] + RNG.uniform(-0.5, 0.5)
        rv_lon = g["lon"] + RNG.uniform(-0.5, 0.5)
    else:
        rv_lat = RNG.uniform(bbox[1] + 1, bbox[3] - 1)
        rv_lon = RNG.uniform(bbox[0] + 1, bbox[2] - 1)

    tracks = []
    # Fishing vessel: was already fishing, pauses for transshipment, resumes
    mmsi_fish = 750_000_001 + event_idx * 100 + (hash(region_key) % 1_000)
    sequence_fish = [
        ("fishing",       8),
        ("transshipment", 3),
        ("fishing",       6),
        ("transit",       5),
    ]
    dark_segs_fish = []
    if RNG.random() < 0.5:
        # Goes dark just before/during transfer — common IUU behaviour
        dark_segs_fish = [(8/22, 11/22)]

    tracks.append(_build_track(
        mmsi=mmsi_fish, vessel_key="trawler",
        start_lat=rv_lat + RNG.uniform(-0.3, 0.3),
        start_lon=rv_lon + RNG.uniform(-0.3, 0.3),
        start_time=start_time,
        duration_hours=22,
        activity_sequence=sequence_fish,
        dark_segments=dark_segs_fish,
        flag=RNG.choice(["CN", "TW", "KR", "VU"]),
        name=f"FISH_{region_key[:3].upper()}_TRANS",
    ))

    # Reefer carrier: transits in, meets fishing vessel, departs for port
    mmsi_reefer = 750_100_001 + event_idx * 100 + (hash(region_key) % 1_000)
    sequence_reefer = [
        ("transit",       6),
        ("transshipment", 3),
        ("transit",       8),
    ]
    tracks.append(_build_track(
        mmsi=mmsi_reefer, vessel_key="reefer_carrier",
        start_lat=rv_lat + RNG.uniform(-1.5, 1.5),
        start_lon=rv_lon + RNG.uniform(-1.5, 1.5),
        start_time=start_time,
        duration_hours=17,
        activity_sequence=sequence_reefer,
        dark_segments=[],
        flag=RNG.choice(["PA", "MH", "LR"]),
        name=f"REEFER_{region_key[:3].upper()}_01",
    ))

    return pd.concat(tracks, ignore_index=True)


def simulate_bunkering(region_key: str, event_idx: int = 0) -> pd.DataFrame:
    """
    Simulate a bunkering (fuel supply) operation at a port approach anchorage.

    A bunker barge approaches a large cargo vessel waiting at anchor.
    Dwell is short (1-2h); both vessels then depart in different directions.
    Common near major waypoints (Singapore Strait, off Lagos, Santos).
    """
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    ports  = region.get("primary_ports", [])
    start_time = datetime(2024, 6, 5, 4, 0, 0) + timedelta(hours=event_idx * 14)

    # Near a port approach anchorage
    if ports:
        p = RNG.choice(ports)
        anch_lat = p["lat"] + RNG.uniform(0.1, 0.4) * RNG.choice([-1, 1])
        anch_lon = p["lon"] + RNG.uniform(0.1, 0.4) * RNG.choice([-1, 1])
    else:
        bbox = region["bbox"]
        anch_lat = RNG.uniform(bbox[1], bbox[3])
        anch_lon = RNG.uniform(bbox[0], bbox[2])

    tracks = []

    # Cargo vessel: slows to anchor, bunkers, departs
    mmsi_cargo = 760_000_001 + event_idx * 100 + (hash(region_key) % 1_000)
    sequence_cargo = [
        ("transit",   4),
        ("anchored",  1),
        ("bunkering", 2),
        ("anchored",  0.5),
        ("transit",   6),
    ]
    tracks.append(_build_track(
        mmsi=mmsi_cargo, vessel_key="cargo",
        start_lat=anch_lat + RNG.uniform(-1, 1),
        start_lon=anch_lon + RNG.uniform(-1, 1),
        start_time=start_time,
        duration_hours=13.5,
        activity_sequence=sequence_cargo,
        dark_segments=[],
        flag=RNG.choice(["CN", "KR", "SG", "JP"]),
        name=f"CARGO_{region_key[:3].upper()}_BNKR",
    ))

    # Bunker barge: transits from port, bunkers, returns
    mmsi_barge = 760_100_001 + event_idx * 100 + (hash(region_key) % 1_000)
    sequence_barge = [
        ("transit",   2),
        ("bunkering", 2),
        ("transit",   2),
    ]
    tracks.append(_build_track(
        mmsi=mmsi_barge, vessel_key="bunker_barge",
        start_lat=anch_lat + RNG.uniform(-0.2, 0.2),
        start_lon=anch_lon + RNG.uniform(-0.2, 0.2),
        start_time=start_time + timedelta(hours=5),   # arrives after cargo is anchored
        duration_hours=6,
        activity_sequence=sequence_barge,
        dark_segments=[],
        flag=RNG.choice(["SG", "MY", "BR", "NG"]),
        name=f"BARGE_{region_key[:3].upper()}_01",
    ))

    return pd.concat(tracks, ignore_index=True)


def _build_survey_track(
    mmsi: int,
    start_lat: float,
    start_lon: float,
    start_time: datetime,
    n_lines: int = 6,
    line_len_nm: float = 12.0,
    line_spacing_nm: float = 1.0,
    survey_sog: float = 4.0,
    transit_sog: float = 12.0,
    flag: str = "US",
    name: str = "SURVEY_01",
    dt_sec: int = 300,
) -> pd.DataFrame:
    """
    Build a parallel-line survey track (seismic or hydrographic).
    Produces the characteristic comb pattern: N lines, each separated by
    a wide 180° arc turn.  Transit legs bookend the survey block.
    """
    tmpl = VESSEL_TEMPLATES["survey_vessel"]
    length = RNG.integers(*tmpl["length_range"])
    width  = RNG.integers(*tmpl["width_range"])
    draught = round(RNG.uniform(*tmpl["draught_range"]), 1)

    records = []
    lat, lon = start_lat, start_lon
    t = start_time

    def _add_leg(la, lo, cog, sog, dur_h, activity, nav_s):
        nonlocal t
        n_steps = max(1, int(dur_h * 3600 / dt_sec))
        cur_lat, cur_lon, cur_cog = la, lo, cog
        for _ in range(n_steps):
            reported_sog = max(0.0, sog + RNG.normal(0, 0.15))
            records.append({
                "mmsi": mmsi, "vessel_type_key": "survey_vessel",
                "vessel_type_code": tmpl["type_code"],
                "timestamp": t,
                "lat": round(cur_lat + RNG.normal(0, 0.0001), 5),
                "lon": round(cur_lon + RNG.normal(0, 0.0001), 5),
                "sog": round(reported_sog, 1),
                "cog": round(cur_cog, 1),
                "heading": round(cur_cog + RNG.normal(0, 1), 1) % 360,
                "nav_status": nav_s,
                "length": int(length), "width": int(width), "draught": draught,
                "name": name, "flag": flag,
                "ais_on": True,
                "true_activity": activity,
                "had_dark_period": False,
            })
            cur_lat, cur_lon = _step(cur_lat, cur_lon, sog, cur_cog, dt_sec)
            cur_cog = (cur_cog + RNG.normal(0, 1.5)) % 360   # tight line
            t += timedelta(seconds=dt_sec)
        return cur_lat, cur_lon

    # Transit to survey area
    lat, lon = _add_leg(lat, lon, 90, transit_sog, 1.0, "transit",
                        NAV_STATUS["underway_engine"])

    cog = 0.0   # first line heads north
    spacing_deg = line_spacing_nm / 60.0

    for line_idx in range(n_lines):
        dur_h = line_len_nm / survey_sog
        lat, lon = _add_leg(lat, lon, cog, survey_sog, dur_h, "survey",
                            NAV_STATUS["restricted_maneuverability"])

        if line_idx < n_lines - 1:
            # Wide arc turn: offset to next line then reverse
            turn_cog = (cog + 90) % 360
            lat, lon = _add_leg(lat, lon, turn_cog, survey_sog * 0.7, 0.25,
                                "transit", NAV_STATUS["underway_engine"])
            lat += spacing_deg * (1 if cog < 180 else -1)
            cog = (cog + 180) % 360  # reverse direction

    # Transit back
    _add_leg(lat, lon, 180, transit_sog, 1.0, "transit",
             NAV_STATUS["underway_engine"])

    return pd.DataFrame(records)


def simulate_survey(region_key: str, n_vessels: int = 1) -> pd.DataFrame:
    """
    Simulate seismic / hydrographic survey operations in a region.
    Survey vessels produce a characteristic parallel-comb track pattern at
    very low speed (3-5 kn), which can be confused with slow fishing.
    """
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    start_time = datetime(2024, 6, 6, 0, 0, 0)
    tracks = []
    for i in range(n_vessels):
        mmsi = 770_000_001 + i + (hash(region_key) % 10_000)
        start_lat = RNG.uniform(bbox[1] + 0.5, bbox[3] - 0.5)
        start_lon = RNG.uniform(bbox[0] + 0.5, bbox[2] - 0.5)
        flag = RNG.choice(["US", "NO", "GB", "AU"])
        tracks.append(_build_survey_track(
            mmsi=mmsi,
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time + timedelta(hours=RNG.uniform(0, 6)),
            n_lines=RNG.integers(4, 8),
            line_len_nm=RNG.uniform(8, 16),
            line_spacing_nm=RNG.uniform(0.8, 1.5),
            survey_sog=RNG.uniform(3.5, 5.0),
            flag=flag,
            name=f"SURVEY_{region_key[:3].upper()}_{i:02d}",
        ))
    return pd.concat(tracks, ignore_index=True)


def _build_patrol_track(
    mmsi: int,
    start_lat: float,
    start_lon: float,
    start_time: datetime,
    patrol_area_nm: float = 15.0,
    patrol_sog: float = 10.0,
    flag: str = "XX",
    name: str = "PATROL_01",
    dt_sec: int = 300,
) -> pd.DataFrame:
    """
    Build an expanding-square patrol track.  Each successive leg is longer
    than the previous by one step width.  Classic SAR / coast-guard pattern.
    """
    tmpl = VESSEL_TEMPLATES["patrol_vessel"]
    length = RNG.integers(*tmpl["length_range"])
    width  = RNG.integers(*tmpl["width_range"])
    draught = round(RNG.uniform(*tmpl["draught_range"]), 1)

    records = []
    lat, lon = start_lat, start_lon
    t = start_time
    cog = 0.0
    step_nm = patrol_area_nm / 10.0

    for leg in range(16):   # 16 legs ≈ 4 expanding squares
        leg_nm = step_nm * (1 + leg // 2)
        n_pings = max(1, int(leg_nm / patrol_sog * 3600 / dt_sec))
        activity = "patrol_sweep"
        nav_s = NAV_STATUS["underway_engine"]

        for _ in range(n_pings):
            reported_sog = max(0.0, patrol_sog + RNG.normal(0, 0.5))
            records.append({
                "mmsi": mmsi, "vessel_type_key": "patrol_vessel",
                "vessel_type_code": tmpl["type_code"],
                "timestamp": t,
                "lat": round(lat + RNG.normal(0, 0.0002), 5),
                "lon": round(lon + RNG.normal(0, 0.0002), 5),
                "sog": round(reported_sog, 1),
                "cog": round(cog, 1),
                "heading": round(cog + RNG.normal(0, 2), 1) % 360,
                "nav_status": nav_s,
                "length": int(length), "width": int(width), "draught": draught,
                "name": name, "flag": flag,
                "ais_on": True,
                "true_activity": activity,
                "had_dark_period": False,
            })
            lat, lon = _step(lat, lon, patrol_sog, cog, dt_sec)
            t += timedelta(seconds=dt_sec)

        cog = (cog + 90) % 360   # 90° turn at end of each leg

    return pd.DataFrame(records)


def simulate_patrol(region_key: str, n_vessels: int = 2) -> pd.DataFrame:
    """
    Simulate coast-guard / EEZ patrol vessels doing expanding-square sweeps.
    """
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    bbox = region["bbox"]
    start_time = datetime(2024, 6, 7, 6, 0, 0)
    tracks = []
    flags = {"brazil_eez": "BR", "philippines_eez": "PH",
             "strait_of_malacca": "SG", "gulf_of_guinea": "NG"}
    flag = flags.get(region_key, "XX")
    for i in range(n_vessels):
        mmsi = 780_000_001 + i + (hash(region_key) % 10_000)
        start_lat = RNG.uniform(bbox[1] + 1, bbox[3] - 1)
        start_lon = RNG.uniform(bbox[0] + 1, bbox[2] - 1)
        tracks.append(_build_patrol_track(
            mmsi=mmsi,
            start_lat=start_lat, start_lon=start_lon,
            start_time=start_time + timedelta(hours=RNG.uniform(0, 4)),
            patrol_area_nm=RNG.uniform(10, 20),
            patrol_sog=RNG.uniform(8, 14),
            flag=flag,
            name=f"PATROL_{region_key[:3].upper()}_{i:02d}",
        ))
    return pd.concat(tracks, ignore_index=True)


def simulate_dredging(region_key: str, n_vessels: int = 1) -> pd.DataFrame:
    """
    Simulate dredging operations at a port entrance channel.
    Dredgers run back-and-forth at 1-2.5 kn along a narrow channel axis,
    with short repositioning transits at the channel ends.
    """
    from ..util.regions import REGIONS
    region = REGIONS[region_key]
    ports  = region.get("primary_ports", [])
    start_time = datetime(2024, 6, 8, 0, 0, 0)

    if ports:
        p = RNG.choice(ports)
        ch_lat = p["lat"]
        ch_lon = p["lon"]
    else:
        bbox = region["bbox"]
        ch_lat = RNG.uniform(bbox[1], bbox[3])
        ch_lon = RNG.uniform(bbox[0], bbox[2])

    tracks = []
    for i in range(n_vessels):
        mmsi = 790_000_001 + i + (hash(region_key) % 10_000)
        flag = RNG.choice(["NL", "BE", "US", "SG"])

        # Build back-and-forth dredging track
        tmpl = VESSEL_TEMPLATES["dredger"]
        length = RNG.integers(*tmpl["length_range"])
        width  = RNG.integers(*tmpl["width_range"])
        draught = round(RNG.uniform(*tmpl["draught_range"]), 1)
        dredge_sog = RNG.uniform(1.0, 2.5)
        channel_len_nm = RNG.uniform(1.5, 3.5)
        dt_sec = 300
        n_passes = RNG.integers(6, 12)
        records = []
        lat, lon = ch_lat + RNG.uniform(-0.05, 0.05), ch_lon + RNG.uniform(-0.05, 0.05)
        t = start_time + timedelta(hours=RNG.uniform(0, 4))
        cog = RNG.uniform(0, 360)

        for pass_idx in range(n_passes):
            n_pings = max(2, int(channel_len_nm / dredge_sog * 3600 / dt_sec))
            for _ in range(n_pings):
                records.append({
                    "mmsi": mmsi, "vessel_type_key": "dredger",
                    "vessel_type_code": tmpl["type_code"],
                    "timestamp": t,
                    "lat": round(lat + RNG.normal(0, 0.0001), 5),
                    "lon": round(lon + RNG.normal(0, 0.0001), 5),
                    "sog": round(max(0.0, dredge_sog + RNG.normal(0, 0.2)), 1),
                    "cog": round((cog + RNG.normal(0, 3)) % 360, 1),
                    "heading": round((cog + RNG.normal(0, 4)) % 360, 1),
                    "nav_status": NAV_STATUS["restricted_maneuverability"],
                    "length": int(length), "width": int(width), "draught": draught,
                    "name": f"DREDGER_{region_key[:3].upper()}_{i:02d}",
                    "flag": flag,
                    "ais_on": True,
                    "true_activity": "dredging",
                    "had_dark_period": False,
                })
                lat, lon = _step(lat, lon, dredge_sog, cog, dt_sec)
                t += timedelta(seconds=dt_sec)
            # Reposition at end of pass
            cog = (cog + 180) % 360
            for _ in range(3):
                records.append({
                    "mmsi": mmsi, "vessel_type_key": "dredger",
                    "vessel_type_code": tmpl["type_code"],
                    "timestamp": t,
                    "lat": round(lat + RNG.normal(0, 0.0001), 5),
                    "lon": round(lon + RNG.normal(0, 0.0001), 5),
                    "sog": round(4.0 + RNG.normal(0, 0.3), 1),
                    "cog": round(cog, 1),
                    "heading": round(cog, 1),
                    "nav_status": NAV_STATUS["underway_engine"],
                    "length": int(length), "width": int(width), "draught": draught,
                    "name": f"DREDGER_{region_key[:3].upper()}_{i:02d}",
                    "flag": flag,
                    "ais_on": True,
                    "true_activity": "transit",
                    "had_dark_period": False,
                })
                lat, lon = _step(lat, lon, 4.0, cog, dt_sec)
                t += timedelta(seconds=dt_sec)

        tracks.append(pd.DataFrame(records))
    return pd.concat(tracks, ignore_index=True)


def simulate_region(region_key: str) -> pd.DataFrame:
    """Generate a complete mixed simulation for a region."""
    parts = [
        simulate_fishing_fleet(region_key, n_vessels=20, duration_hours=72),
        simulate_cargo_traffic(region_key, n_vessels=12, duration_hours=48),
        # 3 STS events per region (no dark masking — labels always visible)
        simulate_sts_event(region_key, event_idx=0),
        simulate_sts_event(region_key, event_idx=1),
        simulate_sts_event(region_key, event_idx=2),
        simulate_loiterers(region_key, n_vessels=4),
        simulate_anchored_fleet(region_key, n_vessels=5),
        # 3 transshipment events per region
        simulate_transshipment(region_key, event_idx=0),
        simulate_transshipment(region_key, event_idx=1),
        simulate_transshipment(region_key, event_idx=2),
        # 3 bunkering events per region
        simulate_bunkering(region_key, event_idx=0),
        simulate_bunkering(region_key, event_idx=1),
        simulate_bunkering(region_key, event_idx=2),
        simulate_survey(region_key, n_vessels=1),
        simulate_patrol(region_key, n_vessels=2),
        simulate_dredging(region_key, n_vessels=1),
    ]
    df = pd.concat(parts, ignore_index=True)
    df["region"] = region_key
    return df
