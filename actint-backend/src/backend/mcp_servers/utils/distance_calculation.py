import math



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


def calculate_sog(lat1: float, lon1: float, time1: float, lat2: float, lon2: float, time2: float) -> float:
    """Calculate speed over ground in knots.
    
    Time 1 and time 2 are datetime objects"""
    distance_nm = haversine_distance_nm(lat1, lon1, lat2, lon2)
    time_hours = (time2 - time1).total_seconds() / 3600.0
    if time_hours > 0:
        return distance_nm / time_hours
    else:
        return 0.0