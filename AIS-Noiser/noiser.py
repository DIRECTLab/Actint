import math, random
from datetime import datetime, timedelta
from Settings import Settings

def noise_coordinate(lat: float, lon: float, distance_m_lat: float, distance_m_lon: float, alt: float = None, distance_m_alt: float = 0, is_2d: bool = True) -> tuple[float, float]:
    """
    Adds random noise up to distance_m in both lat and lon directions and altitude if applicable.
    
    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        alt: Altitude in meters.
        distance_m_latitude: Maximum noise distance in meters for the latitude in decimal degrees.
        distance_m_longitude: Maximum noise distance in meters for the latitude in decimal degrees.
        distance_m_altitude: Maximum noise distance in meters for the altitude.
        
    Returns:
        A tuple of (noised_lat, noised_lon) if altitude is not provided.
        A tuple of (noised_lat, noised_lon, noised_alt) if altitude is provided.
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


    if is_2d:
        return noised_lat, noised_lon
    else:
        offset_z = random.uniform(-distance_m_alt, distance_m_alt)
        noised_alt = alt + offset_z
        return noised_lat, noised_lon, noised_alt

def noise_time(**kwargs) -> str:
    """
    Adds random noise to a timestamp in seconds.

    Args:
        datetime: Original timestamp as a string in ISO 8601 format.
        date: Original date as a string in 'YYYY-MM-DD' format.
        time: Original time as a string in 'HH:MM:SS' format.
        settings: Settings object containing noise parameters.
    Returns:
        Noised timestamp as an ISO 8601 formatted string.
    """
    settings = kwargs['settings']
    noise = random.uniform(-settings.noise_time, 0) if not settings.noise_time_backward else random.uniform(-settings.noise_time, settings.noise_time)
    if 'datetime' in kwargs:
        time = datetime.fromisoformat(kwargs['datetime']) + timedelta(seconds=noise)
    else:
        time = datetime.fromisoformat(kwargs['date'] + " " + kwargs['time']) - timedelta(seconds=noise)
    return time.isoformat(sep=' ', timespec='seconds')




if __name__ == "__main__":
  # Example usage
  original_lat, original_lon = 35.6895, 139.6917  # Tokyo coordinates
  noised = noise_coordinate(original_lat, original_lon, 100.0, 100.0)
  print(f"Original: {original_lat}, {original_lon}")
  print(f"Noised: {noised[0]}, {noised[1]}")