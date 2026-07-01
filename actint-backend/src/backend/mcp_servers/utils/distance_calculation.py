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


def get_cross_track_distance(lat1, lon1, lat2, lon2, lat3, lon3, r=3440.065):
    """
      Args:
        lat1, lon1: start point of the great circle.
        lat2, lon2: end point of the great circle.
        lat3, lon3: test point.
    Returns:
        dxt: float - great cicle distance between point P3 to the closest point
                  on great circle that connects P1 and P2. positive means right side, neg means left side of track
    """
    # detect point segment (P1 == P2)
    if lat1 == lat2 and lon1 == lon2:
        # fallback: distance from P1 to P3
        return haversine_distance_nm(lat1, lon1, lat3, lon3)
    
    # angular distance P1 → P3
    delta13 = haversine_distance_nm(lat1, lon1, lat3, lon3) / r

    # bearings
    theta13 = math.radians(calculate_bearing(lat1, lon1, lat3, lon3))
    theta12 = math.radians(calculate_bearing(lat1, lon1, lat2, lon2))

    x = math.sin(delta13) * math.sin(theta13 - theta12)

    # numerical safety clamp
    x = max(-1.0, min(1.0, x))

    dtheta = math.asin(x)

    return r * dtheta


def rdp(points, epsilon):
    """
    Ramer-Douglas-Peucker simplification for lat/lon points.

    Args:
        points: list of (lat, lon)
        epsilon: max cross-track deviation in nautical miles

    Returns:
        simplified list of (lat, lon)
    """

    if len(points) < 3:
        return points

    # find point with max deviation from segment (start → end)
    start = points[0]
    end = points[-1]

    max_dist = 0.0
    index = 0

    for i in range(1, len(points) - 1):
        lat3, lon3 = points[i]

        d = abs(
            get_cross_track_distance(
                start[0], start[1],
                end[0], end[1],
                lat3, lon3
            )
        )

        if d > max_dist:
            max_dist = d
            index = i

    # recursive decision
    if max_dist > epsilon:
        # split and recurse
        left = rdp(points[:index + 1], epsilon)
        right = rdp(points[index:], epsilon)

        # merge (avoid duplicate midpoint)
        return left[:-1] + right

    else:
        # discard intermediate points
        return [start, end]