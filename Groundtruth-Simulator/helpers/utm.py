from pyproj import CRS, Transformer, Geod

# Initialize a WGS84 ellipsoid for geodesic calculations once
geod = Geod(ellps='WGS84')

# These are the utm conversion functions that would typically come from helpers.utm
# (using the robust versions from previous iterations)
def latlon_to_utm(latitude, longitude):
    """
    Convert latitude and longitude to UTM coordinates.
    Parameters:
- latitude: The latitude in decimal degrees.
- longitude: The longitude in decimal degrees.
Returns:
- easting: The easting (x) coordinate in meters.
- northing: The northing (y) coordinate in meters.
- zone_number: The UTM zone number (1-60).
- zone_letter: The UTM zone letter (C-X, excluding I and O).
    """
    zone_number = ((int((longitude + 180) / 6) +60) % 60) + 1  # Wrap around to ensure 1..60
    zone_letters = "CDEFGHJKLMNPQRSTUVWXX"
    zone_letter = 'N' # This needs to be correctly determined by actual latitude
    if -80 <= latitude < 84:
        zone_letter_index = int((latitude + 80) / 8)
        zone_letter = zone_letters[min(zone_letter_index, len(zone_letters)-1)]
    else: # Handle polar regions outside standard UTM bands, approximately
        if latitude >= 0:
            zone_letter = 'X'
        else:
            zone_letter = 'C'

    if latitude >= 0:
        utm_crs_str = f"+proj=utm +zone={zone_number} +north +datum=WGS84"
    else:
        utm_crs_str = f"+proj=utm +zone={zone_number} +south +datum=WGS84"
    wgs84_crs = CRS.from_epsg(4326)
    utm_crs = CRS.from_string(utm_crs_str)
    transformer = Transformer.from_crs(wgs84_crs, utm_crs, always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)
    return easting, northing, zone_number, zone_letter

def utm_to_latlon(easting, northing, zone_number, zone_letter=None):
    """
    Convert UTM coordinates to latitude and longitude.
    Parameters:
- easting: The easting (x) coordinate in meters.
- northing: The northing (y) coordinate in meters.
- zone_number: The UTM zone number (1-60).
- zone_letter: The UTM zone letter (C-X, excluding I and O). Optional but recommended for accuracy.
Returns:
- latitude: The latitude in decimal degrees.
- longitude: The longitude in decimal degrees.
    """
    if zone_letter!=None and zone_letter.upper() >= 'N':
        utm_crs_str = f"+proj=utm +zone={zone_number} +north +datum=WGS84"
    elif zone_letter:
        utm_crs_str = f"+proj=utm +zone={zone_number} +south +datum=WGS84"
    else: # Fallback if no letter, assume north, but warn if ambiguous
        print("Warning: utm_to_latlon called without zone_letter, assuming Northern Hemisphere.")
        utm_crs_str = f"+proj=utm +zone={zone_number} +north +datum=WGS84"
    utm_crs = CRS.from_string(utm_crs_str)
    wgs84_crs = CRS.from_epsg(4326)
    transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)
    longitude, latitude = transformer.transform(easting, northing)
    return latitude, longitude

def latlon_dist(pos1, pos2) -> float:
    """
Calculate the geodesic distance between two positions using pyproj's Geod.
Parameters:
- pos1: The first position (must have .latitude and .longitude).
- pos2: The second position (must have .latitude and .longitude).
Returns:
- distance: The geodesic distance in meters between the two positions.
    """
    if pos1.__class__ != pos2.__class__:
        raise TypeError("Both positions must be of the same type")

    # assuming Position has .latitude and .longitude
    lon1, lat1 = pos1.longitude, pos1.latitude
    lon2, lat2 = pos2.longitude, pos2.latitude

    az12, az21, distance = geod.inv(lon1, lat1, lon2, lat2)

    return distance  # meters

def same_utm_zone(pos1, pos2) -> bool:
    """Check if two positions are in the same UTM zone."""
    if pos1.__class__ != pos2.__class__:
        raise TypeError("Both positions must be of the same type")
    eating1, northing1, number1, letter1 = latlon_to_utm(pos1.latitude, pos1.longitude)
    eating2, northing2, number2, letter2 = latlon_to_utm(pos2.latitude, pos2.longitude)

    return (has_valid_utm(number1, letter1) and has_valid_utm(number2, letter2) and number1 == number2 and letter1 == letter2)

def has_valid_utm(number, letter) -> bool:
    return number != 0 and bool(letter)


def utm_zone_projection(zone_number, zone_letter, latitude, longitude):
    """Project a lat/lon point to UTM coordinates for a specific zone."""
    if zone_number is None:
        raise ValueError("zone_number is required")
    zone_number = int(zone_number)
    if not (1 <= zone_number <= 60):
        raise ValueError(f"Invalid UTM zone_number {zone_number}. Expected 1..60.")

    if not zone_letter:
        raise ValueError("zone_letter is required to determine hemisphere")
    zone_letter = str(zone_letter).strip().upper()

    # UTM zone letters N..X indicate Northern hemisphere; C..M indicate Southern.
    hemisphere_flag = "north" if zone_letter >= 'N' else "south"
    utm_crs_str = f"+proj=utm +zone={zone_number} +{hemisphere_flag} +datum=WGS84"

    wgs84_crs = CRS.from_epsg(4326)
    utm_crs = CRS.from_string(utm_crs_str)
    transformer = Transformer.from_crs(wgs84_crs, utm_crs, always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)
    return easting, northing