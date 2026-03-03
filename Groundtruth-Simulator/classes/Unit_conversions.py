import numpy as np
from .Settings import Settings

# WGS‑84 ellipsoid constants
a = 6378137.0            # semi-major axis (meters)
f = 1 / 298.257223563    # flattening
e2 = 2*f - f**2          # eccentricity squared


def geodetic_to_ecef(lat, lon, h):
  """
  Convert geodetic coordinates (radians, radians, meters)
  to ECEF (meters).
  """
  sin_lat = np.sin(lat)
  cos_lat = np.cos(lat)
  sin_lon = np.sin(lon)
  cos_lon = np.cos(lon)

  N = a / np.sqrt(1 - e2 * sin_lat**2)

  X = (N + h) * cos_lat * cos_lon
  Y = (N + h) * cos_lat * sin_lon
  Z = (N * (1 - e2) + h) * sin_lat

  return np.array([X, Y, Z])


def enu_to_ecef_matrix(lat, lon):
  """
  Rotation matrix from local ENU frame to ECEF.
  """
  sin_lat = np.sin(lat)
  cos_lat = np.cos(lat)
  sin_lon = np.sin(lon)
  cos_lon = np.cos(lon)

  # Columns are East, North, Up unit vectors in ECEF
  R = np.array([
    [-sin_lon,              -sin_lat*cos_lon,   cos_lat*cos_lon],
    [ cos_lon,              -sin_lat*sin_lon,   cos_lat*sin_lon],
    [       0,                       cos_lat,            sin_lat]
  ])

  return R


def enu_to_ecef(enu, lat0, lon0, h0):
  """
  Convert a local ENU vector to global ECEF coordinates.
  enu: np.array([e, n, u])
  lat0, lon0 in radians
  h0 in meters
  """
  # ECEF of the ENU origin
  origin_ecef = geodetic_to_ecef(lat0, lon0, h0)

  # Rotation matrix
  R = enu_to_ecef_matrix(lat0, lon0)

  # Apply transform
  return origin_ecef + R @ enu


def ecef_to_geodetic(X, Y, Z):
  """
  Convert ECEF coordinates (meters) to geodetic coordinates.
  Returns (latitude, longitude, height) in (radians, radians, meters).
  Uses iterative algorithm for latitude calculation.
  """
  # Longitude is straightforward
  lon = np.arctan2(Y, X)
  
  # Latitude requires iteration
  p = np.sqrt(X**2 + Y**2)
  lat = np.arctan2(Z, p * (1 - e2))
  
  # Iterate to refine latitude
  for _ in range(5):
    N = a / np.sqrt(1 - e2 * np.sin(lat)**2)
    lat = np.arctan2(Z + e2 * N * np.sin(lat), p)
  
  # Calculate height
  N = a / np.sqrt(1 - e2 * np.sin(lat)**2)
  h = p / np.cos(lat) - N
  
  return lat, lon, h


# Simulation reference point (origin) - Just east of Hawaii
# Change these to match your simulation area
# Accuracy by Distance. If the origin is too far from the area of interest, accuracy degrades:
# 0-10 km: Sub-meter errors - excellent for harbor/port simulations
# 10-50 km: 1-10 meter errors - good for coastal areas
# 50-100 km: 10-50 meter errors - acceptable for regional simulations
# 100-200 km: 50-200 meter errors - marginal accuracy
# 200+ km: 200+ meter errors - significant distortion
ORIGIN_LAT = 20.590305   # ~20.59°N latitude (degrees)
ORIGIN_LON = -157.697742   # ~157.70°W longitude (degrees)
ORIGIN_HEIGHT = 0.0              # Sea level
  

def ecef_to_enu(ecef: np.ndarray, lat0: float, lon0: float, h0: float) -> np.ndarray:
  """Convert ECEF coordinates (meters) to a local ENU vector (meters).

  Args:
    ecef: np.array([X, Y, Z]) in meters
    lat0, lon0: origin geodetic coordinates in radians
    h0: origin height in meters

  Returns:
    np.array([e, n, u]) in meters
  """
  origin_ecef = geodetic_to_ecef(lat0, lon0, h0)
  delta = np.asarray(ecef, dtype=float) - origin_ecef
  R = enu_to_ecef_matrix(lat0, lon0)
  return R.T @ delta


def geodetic_to_local(latitude_deg: float, longitude_deg: float, height_m: float = 0.0, settings: Settings | None = None) -> tuple[float, float, float]:
  """Convert geodetic coordinates (degrees) to local ENU coordinates (meters).

  This is the inverse of `local_to_geodetic`.

  Args:
    latitude_deg: latitude in degrees
    longitude_deg: longitude in degrees
    height_m: height above ellipsoid in meters
    settings: simulation Settings; uses `settings.latlon_origin` as the ENU origin

  Returns:
    Tuple of (x_east_m, y_north_m, z_up_m)
  """
  settings = settings or Settings(0, {"latitude": ORIGIN_LAT, "longitude": ORIGIN_LON, "height": ORIGIN_HEIGHT})

  lat_rad = np.radians(latitude_deg)
  lon_rad = np.radians(longitude_deg)
  ecef = geodetic_to_ecef(lat_rad, lon_rad, height_m)

  lat0 = np.radians(settings.latlon_origin["latitude"])
  lon0 = np.radians(settings.latlon_origin["longitude"])
  h0 = settings.latlon_origin["height"]
  enu = ecef_to_enu(ecef, lat0, lon0, h0)

  return float(enu[0]), float(enu[1]), float(enu[2])


def local_to_geodetic(x: float, y: float, z: float = 0.0, settings: Settings | None = None) -> tuple[float, float, float]:
  """
  Convert local ENU coordinates (meters) to geodetic coordinates (degrees).
  
  Args:
    x: East coordinate in meters
    y: North coordinate in meters
    z: Up coordinate in meters (default 0.0 for sea level)
  
  Returns:
    Tuple of (latitude_deg, longitude_deg, height_m)
  """
  settings = settings or Settings(0, {"latitude": ORIGIN_LAT, "longitude": ORIGIN_LON, "height": ORIGIN_HEIGHT})
  # Create ENU vector
  enu = np.array([x, y, z])
  
  # Convert to ECEF
  ecef = enu_to_ecef(enu, np.radians(settings.latlon_origin["latitude"]), np.radians(settings.latlon_origin["longitude"]), settings.latlon_origin["height"])
  
  # Convert to geodetic
  lat_rad, lon_rad, h = ecef_to_geodetic(ecef[0], ecef[1], ecef[2])
  
  # Convert to degrees
  lat_deg = np.degrees(lat_rad)
  lon_deg = np.degrees(lon_rad)
  
  return lat_deg, lon_deg, h