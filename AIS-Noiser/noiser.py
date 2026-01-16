import math
import random

def noise_coordinate(lat: float, lon: float, distance_m_lat: float, distance_m_lon: float) -> tuple[float, float]:
    """
    Adds random noise up to distance_m in both lat and lon directions.
    
    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        distance_m_latitude: Maximum noise distance in meters for the latitude in decimal degrees.
        distance_m_longitude: Maximum noise distance in meters for the latitude in decimal degrees.
        
    Returns:
        A tuple of (noised_lat, noised_lon).
    """
    # Earth Radius in Meters as found in WGS84
    earth_radius = 6_356_752.314245

    # Generate random offsets in meters within the range [-distance_m, distance_m]
    offset_y = random.uniform(-distance_m_lat, distance_m_lat)
    offset_x = random.uniform(-distance_m_lon, distance_m_lon)

    # Convert latitude offset from meters to radians
    d_lat = offset_y / earth_radius
    
    # Convert longitude offset from meters to radians
    # Adjusts for the shrinking distance between meridians near the poles
    d_lon = offset_x / (earth_radius * math.cos(math.radians(lat)))

    # Convert radians back to degrees and add to original coordinates
    noised_lat = lat + math.degrees(d_lat)
    noised_lon = lon + math.degrees(d_lon)

    return noised_lat, noised_lon

if __name__ == "__main__":
  # Example usage
  original_lat, original_lon = 35.6895, 139.6917  # Tokyo coordinates
  noised = noise_coordinate(original_lat, original_lon, 100.0, 100.0)
  print(f"Original: {original_lat}, {original_lon}")
  print(f"Noised: {noised[0]}, {noised[1]}")