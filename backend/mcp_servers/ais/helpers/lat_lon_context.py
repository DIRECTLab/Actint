"""
Latitude/Longitude Context Tool for LLM.

Provides geographic context for coordinates including:
- Reverse geocoding (location names)
- Maritime region identification
- Distance to notable locations (ports, coastlines)
- Bearing and direction calculations
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple
from functools import lru_cache

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False

try:
    import reverse_geocoder as rg
    HAS_REVERSE_GEOCODER = True
except ImportError:
    HAS_REVERSE_GEOCODER = False


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
    "Gulf of Mexico": {
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
    "Panama Canal": (9.1000, -79.6833),
    "Bab el-Mandeb": (12.5833, 43.3333),
    "Taiwan Strait": (24.0000, 119.5000),
    "Strait of Gibraltar": (35.9667, -5.5000),
    "Luzon Strait": (20.0000, 121.0000),
}


@dataclass
class LocationContext:
    """Context information about a geographic location."""
    lat: float
    lon: float
    
    # Reverse geocoding
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    display_name: Optional[str] = None
    
    # Maritime context
    maritime_region: Optional[str] = None
    nearest_port: Optional[str] = None
    distance_to_port_nm: Optional[float] = None
    nearest_waterway: Optional[str] = None
    distance_to_waterway_nm: Optional[float] = None
    
    # Position description
    position_description: Optional[str] = None
    
    def to_context_string(self) -> str:
        """Format as context string for LLM."""
        parts = [f"Location: {self.lat:.4f}°N, {abs(self.lon):.4f}°{'W' if self.lon < 0 else 'E'}"]
        
        if self.display_name:
            parts.append(f"Place: {self.display_name}")
        elif self.country:
            location_parts = [p for p in [self.city, self.region, self.country] if p]
            if location_parts:
                parts.append(f"Place: {', '.join(location_parts)}")
        
        if self.maritime_region:
            parts.append(f"Maritime Region: {self.maritime_region}")
        
        if self.nearest_port and self.distance_to_port_nm is not None:
            parts.append(f"Nearest Major Port: {self.nearest_port} ({self.distance_to_port_nm:.1f} nm)")
        
        if self.nearest_waterway and self.distance_to_waterway_nm is not None:
            parts.append(f"Nearest Strategic Waterway: {self.nearest_waterway} ({self.distance_to_waterway_nm:.1f} nm)")
        
        if self.position_description:
            parts.append(f"Description: {self.position_description}")
        
        return ". ".join(parts)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "lat": self.lat,
            "lon": self.lon,
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "display_name": self.display_name,
            "maritime_region": self.maritime_region,
            "nearest_port": self.nearest_port,
            "distance_to_port_nm": self.distance_to_port_nm,
            "nearest_waterway": self.nearest_waterway,
            "distance_to_waterway_nm": self.distance_to_waterway_nm,
            "position_description": self.position_description,
        }


# ============================================================================
# Distance and Bearing Calculations
# ============================================================================

def haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in nautical miles.
    
    Uses the Haversine formula.
    """
    # Earth radius in nautical miles
    R = 3440.065
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the initial bearing from point 1 to point 2.
    
    Returns bearing in degrees (0-360).
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def bearing_to_cardinal(bearing: float) -> str:
    """Convert bearing in degrees to cardinal direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(bearing / 22.5) % 16
    return directions[index]


def get_relative_position(from_lat: float, from_lon: float, 
                          to_lat: float, to_lon: float, 
                          to_name: str) -> str:
    """Get human-readable relative position description."""
    distance = haversine_distance_nm(from_lat, from_lon, to_lat, to_lon)
    bearing = calculate_bearing(from_lat, from_lon, to_lat, to_lon)
    cardinal = bearing_to_cardinal(bearing)
    
    # Inverse bearing (direction from reference point)
    inverse_bearing = (bearing + 180) % 360
    inverse_cardinal = bearing_to_cardinal(inverse_bearing)
    
    return f"{distance:.0f} nm {inverse_cardinal} of {to_name}"


# ============================================================================
# Maritime Region Identification
# ============================================================================

def identify_maritime_region(lat: float, lon: float) -> Optional[str]:
    """
    Identify the maritime region for given coordinates.
    
    Returns the most specific matching region.
    """
    matches = []
    
    for region_name, region_info in MARITIME_REGIONS.items():
        bounds = region_info["bounds"]
        
        # Handle regions crossing the date line
        if bounds["lon_min"] > bounds["lon_max"]:
            # Region crosses date line (e.g., Bering Sea)
            in_lon = lon >= bounds["lon_min"] or lon <= bounds["lon_max"]
        else:
            in_lon = bounds["lon_min"] <= lon <= bounds["lon_max"]
        
        in_lat = bounds["lat_min"] <= lat <= bounds["lat_max"]
        
        if in_lat and in_lon:
            # Calculate how specific/small the region is (smaller = more specific)
            area = (bounds["lat_max"] - bounds["lat_min"]) * abs(bounds["lon_max"] - bounds["lon_min"])
            matches.append((region_name, area))
    
    if matches:
        # Return most specific (smallest area) match
        matches.sort(key=lambda x: x[1])
        return matches[0][0]
    
    return None


def find_nearest_port(lat: float, lon: float) -> Tuple[str, float]:
    """Find the nearest major port and distance in nautical miles."""
    nearest = None
    min_distance = float('inf')
    
    for port_name, (port_lat, port_lon) in MAJOR_PORTS.items():
        distance = haversine_distance_nm(lat, lon, port_lat, port_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = port_name
    
    return nearest, min_distance


def find_nearest_waterway(lat: float, lon: float) -> Tuple[str, float]:
    """Find the nearest strategic waterway and distance in nautical miles."""
    nearest = None
    min_distance = float('inf')
    
    for waterway_name, (ww_lat, ww_lon) in STRATEGIC_WATERWAYS.items():
        distance = haversine_distance_nm(lat, lon, ww_lat, ww_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = waterway_name
    
    return nearest, min_distance


# ============================================================================
# Reverse Geocoding
# ============================================================================

@lru_cache(maxsize=1000)
def reverse_geocode_nominatim(lat: float, lon: float) -> dict:
    """
    Reverse geocode using OpenStreetMap Nominatim.
    
    Results are cached to avoid repeated API calls.
    """
    if not HAS_GEOPY:
        return {}
    
    try:
        geolocator = Nominatim(user_agent="actint_maritime_intel")
        location = geolocator.reverse(f"{lat}, {lon}", language="en", timeout=5)
        
        if location and location.raw:
            address = location.raw.get("address", {})
            return {
                "display_name": location.raw.get("display_name"),
                "country": address.get("country"),
                "region": address.get("state") or address.get("region"),
                "city": address.get("city") or address.get("town") or address.get("village"),
            }
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    except Exception:
        pass
    
    return {}


@lru_cache(maxsize=1000)
def reverse_geocode_offline(lat: float, lon: float) -> dict:
    """
    Reverse geocode using offline reverse_geocoder library.
    
    Faster but less detailed than Nominatim.
    """
    if not HAS_REVERSE_GEOCODER:
        return {}
    
    try:
        result = rg.search((lat, lon), mode=1)
        if result:
            r = result[0]
            return {
                "city": r.get("name"),
                "region": r.get("admin1"),
                "country": r.get("cc"),
            }
    except Exception:
        pass
    
    return {}


# ============================================================================
# Main Tool Function
# ============================================================================

def get_location_context(
    lat: float, 
    lon: float,
    use_online_geocoding: bool = False,
) -> LocationContext:
    """
    Get comprehensive context for a latitude/longitude location.
    
    This is the main tool function that LLMs can call.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees  
        use_online_geocoding: If True, use Nominatim API (slower but more detailed)
        
    Returns:
        LocationContext with all available information
    """
    context = LocationContext(lat=lat, lon=lon)
    
    # Maritime region
    context.maritime_region = identify_maritime_region(lat, lon)
    
    # Nearest port
    port_name, port_dist = find_nearest_port(lat, lon)
    context.nearest_port = port_name
    context.distance_to_port_nm = round(port_dist, 1)
    
    # Nearest strategic waterway
    waterway_name, waterway_dist = find_nearest_waterway(lat, lon)
    context.nearest_waterway = waterway_name
    context.distance_to_waterway_nm = round(waterway_dist, 1)
    
    # Reverse geocoding
    if use_online_geocoding:
        geo_info = reverse_geocode_nominatim(round(lat, 4), round(lon, 4))
    else:
        geo_info = reverse_geocode_offline(round(lat, 4), round(lon, 4))
    
    if geo_info:
        context.country = geo_info.get("country")
        context.region = geo_info.get("region")
        context.city = geo_info.get("city")
        context.display_name = geo_info.get("display_name")
    
    # Generate position description
    if port_name and port_dist < 50:
        context.position_description = f"Near {port_name}"
    elif port_name:
        port_lat, port_lon = MAJOR_PORTS[port_name]
        context.position_description = get_relative_position(lat, lon, port_lat, port_lon, port_name)
    
    return context


def get_location_context_string(lat: float, lon: float, use_online_geocoding: bool = False) -> str:
    """
    Get location context as a formatted string for LLM prompts.
    
    Convenience wrapper around get_location_context().
    """
    context = get_location_context(lat, lon, use_online_geocoding)
    return context.to_context_string()


def get_distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """
    Calculate distance and bearing between two points.
    
    Tool for LLM to compare vessel positions.
    """
    distance = haversine_distance_nm(lat1, lon1, lat2, lon2)
    bearing = calculate_bearing(lat1, lon1, lat2, lon2)
    cardinal = bearing_to_cardinal(bearing)
    
    return {
        "distance_nm": round(distance, 1),
        "bearing_degrees": round(bearing, 1),
        "bearing_cardinal": cardinal,
        "description": f"{distance:.1f} nm at bearing {bearing:.0f}° ({cardinal})",
    }


# ============================================================================
# Tool definitions for LLM function calling
# ============================================================================

TOOL_DEFINITIONS = [
    {
        "name": "get_location_context",
        "description": "Get geographic and maritime context for a latitude/longitude coordinate. Returns information about the maritime region, nearest port, nearest strategic waterway, and reverse geocoding data.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitude in decimal degrees (e.g., 36.39538)"
                },
                "lon": {
                    "type": "number", 
                    "description": "Longitude in decimal degrees (e.g., -122.66816)"
                },
            },
            "required": ["lat", "lon"]
        }
    },
    {
        "name": "get_distance_between",
        "description": "Calculate the distance and bearing between two geographic points.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat1": {"type": "number", "description": "Latitude of first point"},
                "lon1": {"type": "number", "description": "Longitude of first point"},
                "lat2": {"type": "number", "description": "Latitude of second point"},
                "lon2": {"type": "number", "description": "Longitude of second point"},
            },
            "required": ["lat1", "lon1", "lat2", "lon2"]
        }
    },
]


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Test coordinates
    test_locations = [
        ("USS KIDD example position", 36.39538, -122.66816),
        ("USS MONTGOMERY example position", 32.60973, -117.39904),
        ("USS MILWAUKEE example position", 18.45901, -66.09607),
        ("Mid-Pacific", 25.0, -160.0),
        ("Persian Gulf", 26.5, 51.5),
    ]
    
    print("=" * 70)
    print("Latitude/Longitude Context Tool")
    print("=" * 70)
    
    for name, lat, lon in test_locations:
        print(f"\n{name}:")
        print("-" * 50)
        context = get_location_context(lat, lon)
        print(context.to_context_string())
    
    # Test distance calculation
    print("\n" + "=" * 70)
    print("Distance Calculation Test")
    print("=" * 70)
    
    lat1, lon1 = 36.39538, -122.66816  # USS KIDD
    lat2, lon2 = 32.60973, -117.39904  # USS MONTGOMERY
    
    result = get_distance_between(lat1, lon1, lat2, lon2)
    print(f"\nUSS KIDD to USS MONTGOMERY: {result['description']}")
