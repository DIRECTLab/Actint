"""
EEZ and region definitions for maritime activity intelligence.
Polygons are simplified but geographically representative.
"""

from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
import numpy as np

# ---------------------------------------------------------------------------
# Known fishing grounds, smuggling routes, and strategic chokepoints
# ---------------------------------------------------------------------------

REGIONS = {
    "brazil_eez": {
        "name": "Brazil EEZ",
        "description": "200nm EEZ off Brazil's Atlantic coastline",
        # Simplified bounding box; real EEZ is ~3.5M km²
        "bbox": (-54.0, -35.0, -25.0, 5.5),   # (lon_min, lat_min, lon_max, lat_max)
        "polygon": Polygon([
            (-54.0, -35.0), (-28.0, -35.0), (-25.0, -20.0),
            (-28.0, 5.5),   (-44.0, 5.5),   (-54.0, -10.0),
            (-54.0, -35.0)
        ]),
        "known_activities": ["fishing", "oil_platform_support", "transit", "smuggling"],
        "primary_ports": [
            {"name": "Santos",       "lat": -23.95, "lon": -46.33},
            {"name": "Rio de Janeiro","lat": -22.90, "lon": -43.17},
            {"name": "Fortaleza",    "lat": -3.72,  "lon": -38.52},
        ],
        "oil_fields": [  # Pre-salt / Campos basin centroids
            {"name": "Campos Basin",   "lat": -22.5, "lon": -40.5},
            {"name": "Santos Basin",   "lat": -25.0, "lon": -43.0},
            {"name": "Libra Field",    "lat": -23.8, "lon": -42.0},
        ],
        "fishing_grounds": [
            {"name": "SE Continental Shelf", "lat": -27.0, "lon": -47.0, "radius_nm": 150},
            {"name": "NE Brazil Shelf",      "lat": -4.0,  "lon": -36.0, "radius_nm": 100},
        ],
    },

    "philippines_eez": {
        "name": "Philippines EEZ",
        "description": "200nm EEZ including South China Sea and Philippine Sea",
        "bbox": (116.0, 4.5, 127.5, 21.5),
        "polygon": Polygon([
            (116.0, 9.0),  (116.0, 21.5), (122.0, 21.5),
            (127.5, 15.0), (127.5, 4.5),  (120.0, 4.5),
            (116.0, 9.0)
        ]),
        "known_activities": ["fishing", "transit", "sts_transfer", "illegal_fishing", "naval_patrol"],
        "primary_ports": [
            {"name": "Manila",    "lat": 14.59, "lon": 120.97},
            {"name": "Cebu",      "lat": 10.32, "lon": 123.90},
            {"name": "Davao",     "lat": 7.07,  "lon": 125.60},
            {"name": "Subic Bay", "lat": 14.82, "lon": 120.27},
        ],
        "oil_fields": [
            {"name": "Malampaya",     "lat": 11.5, "lon": 119.5},
            {"name": "SC38 Palawan",  "lat": 9.5,  "lon": 118.5},
        ],
        "fishing_grounds": [
            {"name": "West Philippine Sea",  "lat": 11.0, "lon": 117.5, "radius_nm": 200},
            {"name": "Visayan Sea",          "lat": 11.5, "lon": 123.5, "radius_nm": 80},
            {"name": "Sulu Sea",             "lat": 8.5,  "lon": 121.0, "radius_nm": 120},
        ],
        "disputed_areas": [
            {"name": "Spratly Islands", "lat": 10.5, "lon": 114.5},
            {"name": "Scarborough Shoal","lat": 15.1, "lon": 117.8},
        ],
    },

    "strait_of_malacca": {
        "name": "Strait of Malacca",
        "description": "Critical global chokepoint; ~90k ships/year",
        "bbox": (99.0, 1.0, 104.5, 6.5),
        "polygon": Polygon([
            (99.0, 1.0), (99.0, 6.5), (104.5, 6.5),
            (104.5, 1.0), (99.0, 1.0)
        ]),
        "known_activities": ["transit", "piracy", "sts_transfer", "smuggling"],
        "primary_ports": [
            {"name": "Port Klang",  "lat": 3.0,  "lon": 101.4},
            {"name": "Singapore",   "lat": 1.27, "lon": 103.8},
        ],
    },

    "gulf_of_guinea": {
        "name": "Gulf of Guinea",
        "description": "West African waters; major oil export region, piracy hotspot",
        "bbox": (-5.0, -6.0, 9.0, 6.0),
        "polygon": Polygon([
            (-5.0, -6.0), (-5.0, 6.0), (9.0, 6.0),
            (9.0, -6.0),  (-5.0, -6.0)
        ]),
        "known_activities": ["piracy", "oil_platform_support", "smuggling", "fishing"],
        "primary_ports": [
            {"name": "Lagos",    "lat": 6.45,  "lon": 3.39},
            {"name": "Abidjan", "lat": 5.36,  "lon": -4.02},
        ],
    },
}


def point_in_region(lon: float, lat: float, region_key: str) -> bool:
    region = REGIONS.get(region_key)
    if not region:
        return False
    return region["polygon"].contains(Point(lon, lat))


def nearest_port(lon: float, lat: float, region_key: str) -> dict | None:
    region = REGIONS.get(region_key)
    if not region or "primary_ports" not in region:
        return None
    ports = region["primary_ports"]
    dists = [np.sqrt((p["lon"] - lon)**2 + (p["lat"] - lat)**2) for p in ports]
    return ports[int(np.argmin(dists))]


def nearest_fishing_ground(lon: float, lat: float, region_key: str) -> dict | None:
    region = REGIONS.get(region_key)
    if not region or "fishing_grounds" not in region:
        return None
    grounds = region["fishing_grounds"]
    dists = [np.sqrt((g["lon"] - lon)**2 + (g["lat"] - lat)**2) for g in grounds]
    return grounds[int(np.argmin(dists))]
