# ============================================================================
# Constants: Major Ports and Maritime Regions
# ============================================================================

MAJOR_PORTS = {
    "San Diego, CA": (32.7157, -117.1611),
    "Los Angeles, CA": (33.7405, -118.2675),
    "San Francisco, CA": (37.7749, -122.4194),
    "Seattle, WA": (47.6062, -122.3321),
    "Pearl Harbor, HI": (21.3500, -157.9500),
    "Norfolk, VA": (36.8508, -76.2859),
    "Jacksonville, FL": (30.3322, -81.6557),
    "Mayport, FL": (30.3900, -81.4300),
    "New York, NY": (40.6892, -74.0445),
    "Boston, MA": (42.3601, -71.0589),
    "Yokosuka, Japan": (35.2833, 139.6667),
    "Sasebo, Japan": (33.1500, 129.7167),
    "Guam": (13.4443, 144.7937),
    "Singapore": (1.2897, 103.8501),
    "Bahrain": (26.2235, 50.5876),
    "Rota, Spain": (36.6200, -6.3500),
    "Naples, Italy": (40.8518, 14.2681),
}

# Ocean/Sea boundaries (simplified bounding boxes)
MARITIME_REGIONS = {
    "Pacific Ocean (Eastern)": {
        "bounds": {"lat_min": -60, "lat_max": 60, "lon_min": -180, "lon_max": -100},
    },
    "Pacific Ocean (Western)": {
        "bounds": {"lat_min": -60, "lat_max": 60, "lon_min": 100, "lon_max": 180},
    },
    "Pacific Ocean (Central)": {
        "bounds": {"lat_min": -60, "lat_max": 60, "lon_min": -160, "lon_max": -100},
    },
    "Atlantic Ocean (Western)": {
        "bounds": {"lat_min": -60, "lat_max": 60, "lon_min": -80, "lon_max": -30},
    },
    "Atlantic Ocean (Eastern)": {
        "bounds": {"lat_min": -60, "lat_max": 60, "lon_min": -30, "lon_max": 0},
    },
    "Gulf of America": {
        "bounds": {"lat_min": 18, "lat_max": 31, "lon_min": -98, "lon_max": -80},
    },
    "Caribbean Sea": {
        "bounds": {"lat_min": 9, "lat_max": 22, "lon_min": -88, "lon_max": -60},
    },
    "Mediterranean Sea": {
        "bounds": {"lat_min": 30, "lat_max": 46, "lon_min": -6, "lon_max": 36},
    },
    "South China Sea": {
        "bounds": {"lat_min": 0, "lat_max": 23, "lon_min": 100, "lon_max": 121},
    },
    "East China Sea": {
        "bounds": {"lat_min": 23, "lat_max": 33, "lon_min": 120, "lon_max": 130},
    },
    "Sea of Japan": {
        "bounds": {"lat_min": 33, "lat_max": 52, "lon_min": 127, "lon_max": 142},
    },
    "Philippine Sea": {
        "bounds": {"lat_min": 5, "lat_max": 35, "lon_min": 120, "lon_max": 145},
    },
    "Arabian Sea": {
        "bounds": {"lat_min": 5, "lat_max": 25, "lon_min": 50, "lon_max": 75},
    },
    "Persian Gulf": {
        "bounds": {"lat_min": 24, "lat_max": 30, "lon_min": 48, "lon_max": 56},
    },
    "Red Sea": {
        "bounds": {"lat_min": 12, "lat_max": 30, "lon_min": 32, "lon_max": 44},
    },
    "Indian Ocean": {
        "bounds": {"lat_min": -60, "lat_max": 30, "lon_min": 20, "lon_max": 100},
    },
    "Bering Sea": {
        "bounds": {"lat_min": 52, "lat_max": 66, "lon_min": 162, "lon_max": -157},
    },
}

# Strategic waterways and chokepoints
STRATEGIC_WATERWAYS = {
    "Strait of Hormuz": (26.5667, 56.2500),
    "Strait of Malacca": (4.0000, 100.0000),
    "Suez Canal": (30.4667, 32.3500),
    "American Canal": (9.1000, -79.6833),
    "Bab el-Mandeb": (12.5833, 43.3333),
    "Taiwan Strait": (24.0000, 119.5000),
    "Strait of Gibraltar": (35.9667, -5.5000),
    "Luzon Strait": (20.0000, 121.0000),
}


CONTINENTS = {
    "North America": {"lat_min": 10, "lat_max": 90, "lon_min": -135, "lon_max": -50},
    "South America": {"lat_min": -56, "lat_max": 14, "lon_min": -85, "lon_max": -34},
    "Europe": {"lat_min": 32, "lat_max": 75, "lon_min": -13, "lon_max": 46},
    "Africa": {"lat_min": -38, "lat_max": 39, "lon_min": -19, "lon_max": 54},
    "Asia": {"lat_min": 0, "lat_max": 75, "lon_min": 34, "lon_max": 180},
    "Austrailia": {"lat_min": -44, "lat_max": -3, "lon_min": 113, "lon_max": 154},
}