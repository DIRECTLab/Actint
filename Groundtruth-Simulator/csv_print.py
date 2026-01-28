import pandas as pd
import numpy as np
import datetime
from pathlib import Path
from classes import Settings

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
ORIGIN_LAT = np.radians(20.590305)   # ~20.59°N latitude
ORIGIN_LON = np.radians(-157.697742)   # ~157.70°W longitude  
ORIGIN_HEIGHT = 0.0              # Sea level
  

def local_to_geodetic(x, y, z=0.0, settings: Settings = Settings(0, {"latitude": ORIGIN_LAT, "longitude": ORIGIN_LON, "height": ORIGIN_HEIGHT})) -> tuple:
  """
  Convert local ENU coordinates (meters) to geodetic coordinates (degrees).
  
  Args:
    x: East coordinate in meters
    y: North coordinate in meters
    z: Up coordinate in meters (default 0.0 for sea level)
  
  Returns:
    Tuple of (latitude_deg, longitude_deg, height_m)
  """
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


# Helper function to generate unique filenames for the csv_print_header function.
def _name_file(file: str) -> Path:
  """Generate a unique filename by appending a counter if the file already exists.
  
  Args:
    file: The desired filename as a string.
  
  Returns:
    A Path object with a unique filename. If the original file exists,
    appends "_N" before the extension (e.g., "file.csv" -> "file_1.csv").
  
  Example:
    If "output.csv" exists, returns Path("output_1.csv").
  """
  path = Path(file)
  stem = path.stem
  suffix = path.suffix

  counter = 0
  new_path = path
  while new_path.exists():
    counter += 1
    new_path = path.with_name(f"{stem}_{counter}{suffix}")

  return new_path

def csv_print_header(settings: Settings) -> tuple:
  """Create a new CSV file with headers for vehicle simulation data.
  
  Creates a CSV file matching AIS data format with available simulation fields.
  
  Returns:
    The names of the created CSV files as a tuple of strings (2D filename, 3D filename).
  """
  filename2D = _name_file(settings.output_file_2d).name
  filename3D = _name_file(settings.output_file_3d).name
  
  # Create an empty DataFrame with AIS-like column headers
  df2D = pd.DataFrame(columns=[
    "MMSI",           # Maritime Mobile Service Identity (using vehicle_id)
    "BaseDateTime",   # Timestamp
    "LAT",            # Latitude (using position_y)
    "LON",            # Longitude (using position_x)
    "SOG",            # Speed Over Ground (calculated from velocity)
    "COG",            # Course Over Ground (using heading in degrees)
    "Heading",        # Vessel heading (using heading in degrees)
    "VesselName",     # Vessel name (using vehicle_type)
    "VesselType",     # Type of vessel (using vehicle_type)
    "Length",         # Vessel length (using scale)
    "Width",          # Vessel width (using scale)
  ])

  # Create an empty DataFrame with ADS-B-like column headers
  df3D = pd.DataFrame(columns=[
    "date",                 # date
    "time",                 # time
    "icao_hex",             # ICAO hex (using vehicle_id)
    "latitude",             # Latitude (using position_y)
    "longitude",            # Longitude (using position_x)
    "altitude",             # Altitude (using position_z)
    "altitude_unit",        # Altitude unit (e.g., meters)
    "vertical_rate",        # Vertical rate (using velocity_z)
    "vertical_rate_unit",   # Vertical rate unit (e.g., meters per minute)
  ])
  
  # Write the DataFrame to CSV without index
  if settings.has_vehicle2d:
    df2D.to_csv(filename2D, index=False)
  if settings.has_vehicle3d:
    df3D.to_csv(filename3D, index=False)

  return filename2D, filename3D

def csv_print_data(vehicles: list, filename2D: str, filename3D: str, settings: Settings) -> None:
  """Append vehicle data to an existing CSV file in AIS format.
  
  Extracts vehicle data and writes it in AIS-like format.
  Supports Vehicle2D and Vehicle3D.
  
  Args:
    vehicles: List of vehicle objects.
    filename2D: Path to the 2D CSV file where data should be appended.
    filename3D: Path to the 3D CSV file where data should be appended.
    settings: Settings object containing simulation settings.
    """


  # Convert local coordinates to geodetic and create data rows
  data_rows_2d = []
  data_rows_3d = []
  for v in vehicles:
    # Get altitude for 3D vehicles, default to 0 for 2D
    z = getattr(v, 'pos_z', 0.0)
    
    # Convert local ENU coordinates to geodetic (lat/lon in degrees)
    lat, lon, height = local_to_geodetic(v.pos_x, v.pos_y, z, settings)
    if v.__class__.__name__ == 'Vehicle2D':
      data_rows_2d.append({
        "MMSI": v.vehicle_id,
        "BaseDateTime": settings.current_simulation_time.isoformat(sep=' ', timespec='seconds'),
        "LAT": round(lat, 6),  # Latitude in degrees (~0.1m precision)
        "LON": round(lon, 6),  # Longitude in degrees (~0.1m precision)
        "SOG": round(np.linalg.norm(v.velocity.vector), 3),  # Speed over ground from velocity magnitude
        "COG": round(np.degrees(v.heading) % 360, 3),  # Course over ground in degrees
        "Heading": round(np.degrees(v.heading) % 360, 3),  # Heading in degrees
        "VesselName": v.vehicle_type.upper(),  # Vehicle type as vessel name
        "VesselType": v.vehicle_type,  # Vehicle type
        "Length": round(getattr(v, 'scale', 0.0), 3),  # Using scale as length approximation
        "Width": round(getattr(v, 'scale', 0.0) / 3, 3),  # Approximate width as 1/3 of length
      })
    elif v.__class__.__name__ == 'Vehicle3D':
      data_rows_3d.append({
        "date": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[0],
        "time": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[1],
        "icao_hex": f"{v.vehicle_id:06X}",  # ICAO hex from vehicle_id
        "latitude": round(lat, 6),  # Latitude in degrees (~0.1m precision)
        "longitude": round(lon, 6),  # Longitude in degrees (~0.1m precision)
        "altitude": round(height, 3),  # Altitude in meters
        "altitude_unit": "meters",
        "vertical_rate": round(v.velocity.z * 60, 3),  # Vertical rate in meters per minute
        "vertical_rate_unit": "meters/minute",
      })
  
  # Create DataFrame and append without index
  df_2d = pd.DataFrame(data_rows_2d)
  df_3d = pd.DataFrame(data_rows_3d)
  
  if settings.has_vehicle2d:
    df_2d.to_csv(filename2D, mode='a', header=False, index=False)
  if settings.has_vehicle3d:
    df_3d.to_csv(filename3D, mode='a', header=False, index=False)
