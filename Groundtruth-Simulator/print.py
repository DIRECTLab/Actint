import pandas as pd
import numpy as np
import datetime
import json
from pathlib import Path
from classes import Vehicle, Vehicle2D, Vehicle3D, Settings
from typing import List

# Helper function to generate unique filenames for the csv_print_header function.
def _name_file(settings: Settings) -> tuple[Path | None, Path | None]:
  """Generate unique output filenames (2D/3D) under an `output/` directory.

  - If `settings.output_file_*` is just a filename (no directory), it will be
    written into `output/<name>.<print_format>`.
  - If `settings.output_file_*` already includes a directory, that directory is
    respected.
  - If `settings.output_file_*` already has an extension, it is not duplicated.
  """

  def _build_path(raw_name: str) -> Path:
    base = Path(raw_name)
    if base.suffix:
      filename = base.name
    else:
      filename = f"{base.name}.{settings.print_format}"

    # If caller provided only a filename, force it into ./output
    if base.parent == Path("."):
      return Path("output") / filename

    # Otherwise respect the provided directory.
    return base.parent / filename

  def _unique_path(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    counter = 0
    candidate = path
    while candidate.exists():
      counter += 1
      candidate = path.with_name(f"{stem}_{counter}{suffix}")
    return candidate

  new_path2d: Path | None
  new_path3d: Path | None

  if settings.has_vehicle2d:
    new_path2d = _unique_path(_build_path(settings.output_file_2d))
  else:
    new_path2d = None

  if settings.has_vehicle3d:
    new_path3d = _unique_path(_build_path(settings.output_file_3d))
  else:
    new_path3d = None

  return new_path2d, new_path3d



def csv_print_header(settings: Settings) -> tuple:
  """Create a new CSV file with headers for vehicle simulation data.
  
  Creates a CSV file matching AIS data format with available simulation fields.
  
  Returns:
    The names of the created CSV files as a tuple of strings (2D filename, 3D filename).
  """
  filename2D, filename3D = _name_file(settings)
  
  
  # Create an empty DataFrame with AIS-like column headers
  df2D = pd.DataFrame(columns=[
    "MMSI",           # Maritime Mobile Service Identity (using vehicle_id)
    "BaseDateTime",   # Timestamp
    "LAT",            # Latitude (using latitude property)
    "LON",            # Longitude (using longitude property)
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
    "latitude",             # Latitude (using latitude property)
    "longitude",            # Longitude (using longitude property)
    "altitude",             # Altitude (using position_z)
    "altitude_unit",        # Altitude unit (e.g., meters)
    "vertical_rate",        # Vertical rate (using velocity_z)
    "vertical_rate_unit",   # Vertical rate unit (e.g., meters per minute)
  ])
  
  # Write the DataFrame to CSV without index
  if settings.has_vehicle2d and filename2D is not None:
    Path(filename2D).parent.mkdir(parents=True, exist_ok=True)
    df2D.to_csv(filename2D, index=False)
  if settings.has_vehicle3d and filename3D is not None:
    Path(filename3D).parent.mkdir(parents=True, exist_ok=True)
    df3D.to_csv(filename3D, index=False)

  return filename2D, filename3D

def json_print_header(settings: Settings) -> tuple:
  """Create a new JSON file with headers for vehicle simulation data.
  
  Creates a JSON file matching AIS data format with available simulation fields.
  
  Returns:
    The names of the created JSON files as a tuple of strings (2D filename, 3D filename).
  """
  filename2D, filename3D = _name_file(settings)

  # Initialize files as JSON arrays so json_print_data can append items.
  if settings.has_vehicle2d and filename2D is not None:
    Path(filename2D).parent.mkdir(parents=True, exist_ok=True)
    Path(filename2D).write_text("[\n]\n", encoding="utf-8")
  if settings.has_vehicle3d and filename3D is not None:
    Path(filename3D).parent.mkdir(parents=True, exist_ok=True)
    Path(filename3D).write_text("[\n]\n", encoding="utf-8")

  return filename2D, filename3D

def json_print_data(vehicles: list, filename2D: str, filename3D: str, settings: Settings) -> None:
  """Append vehicle data to JSON files as a single list of dictionaries.

  Each output file remains valid JSON containing one top-level array of objects.
  This mirrors `csv_print_data`, but uses JSON objects instead of CSV rows.
  """

  def _append_json_array(path: str | Path, new_items: list[dict]) -> None:
    if not new_items:
      return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    indent = 4
    if not path.exists() or path.stat().st_size == 0:
      path.write_text("[\n]\n", encoding="utf-8")

    # Append new items inside the closing bracket without loading the whole file.
    with path.open("r+", encoding="utf-8", newline="\n") as f:
      f.seek(0, 2)
      end_pos = f.tell()
      if end_pos == 0:
        f.write("[]\n")
        end_pos = f.tell()

      # Find the closing ']' ignoring trailing whitespace.
      pos = end_pos - 1
      while pos >= 0:
        f.seek(pos)
        ch = f.read(1)
        if ch.isspace():
          pos -= 1
          continue
        if ch != "]":
          raise ValueError(f"Output file {path} is not a JSON array (expected closing ']')")
        break
      if pos < 0:
        raise ValueError(f"Output file {path} is empty/corrupt")

      # Find the last non-whitespace char before the closing ']'.
      last_token_pos = pos - 1
      while last_token_pos >= 0:
        f.seek(last_token_pos)
        ch = f.read(1)
        if ch.isspace():
          last_token_pos -= 1
          continue
        break
      if last_token_pos < 0:
        raise ValueError(f"Output file {path} is empty/corrupt")

      is_empty_array = (ch == "[")

      # Truncate to *after* the last token so we can place the comma right after '}'.
      write_pos = last_token_pos + 1
      f.truncate(write_pos)
      f.seek(write_pos)

      if is_empty_array:
        f.write("\n")
      else:
        f.write(",\n")

      for idx, item in enumerate(new_items):
        item_json = json.dumps(item, ensure_ascii=False, indent=indent)
        item_lines = [(" " * indent) + line for line in item_json.splitlines()]
        if idx < len(new_items) - 1:
          item_lines[-1] = item_lines[-1] + ","
        f.write("\n".join(item_lines))
        f.write("\n")

      f.write("]\n")

  data_rows_2d = []
  data_rows_3d = []
  for v in vehicles:
    if v.done:
      continue  # Skip completed vehicles
    # Get altitude for 3D vehicles, default to 0 for 2D
    z = getattr(v, 'pos_z', 0.0)
    
    # Convert local ENU coordinates to geodetic (lat/lon in degrees)
    if v.__class__.__name__ == 'Vehicle2D':
      data_rows_2d.append({
        "MMSI": v.vehicle_id,
        "BaseDateTime": settings.current_simulation_time.timestamp() if settings.print_time_as == "unix" else settings.current_simulation_time.isoformat(sep=' ', timespec='seconds'),
        "LAT": v.latitude,
        "LON": v.longitude,
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
        "date": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[0] if settings.print_time_as == "iso" else "",  # Date part of ISO timestamp
        "time": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[1] if settings.print_time_as == "iso" else settings.current_simulation_time.timestamp(),
        "icao_hex": f"{v.vehicle_id:06X}",  # ICAO hex from vehicle_id
        "latitude": v.latitude,  # Latitude in degrees (~0.1m precision)
        "longitude": v.longitude,  # Longitude in degrees (~0.1m precision)
        "altitude": round(v.pos_z, 3),  # Altitude in meters
        "altitude_unit": "meters",
        "vertical_rate": round(v.velocity.z * 60, 3),  # Vertical rate in meters per minute
        "vertical_rate_unit": "meters/minute",
      })
  
  # Create DataFrame and append without index
  if settings.has_vehicle2d and filename2D is not None:
    _append_json_array(filename2D, data_rows_2d)
  if settings.has_vehicle3d and filename3D is not None:
    _append_json_array(filename3D, data_rows_3d)

def csv_print_data(vehicles: List[Vehicle], filename2D: str, filename3D: str, settings: Settings) -> None:
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
    if v.done:
      continue  # Skip completed vehicles
    # Get altitude for 3D vehicles, default to 0 for 2D
    z = getattr(v, 'pos_z', 0.0)
    
    # Convert local ENU coordinates to geodetic (lat/lon in degrees)
    # lat, lon, height = local_to_geodetic(v.pos_x, v.pos_y, z, settings)
    if isinstance(v, Vehicle2D):

      data_rows_2d.append({
        "MMSI": v.vehicle_id,
        "BaseDateTime": settings.current_simulation_time.timestamp() if settings.print_time_as == "unix" else settings.current_simulation_time.isoformat(sep=' ', timespec='seconds'),
        "LAT": round(v.latitude, 6),
        "LON": round(v.longitude, 6),
        "SOG": round(np.linalg.norm(v.velocity.vector), 3),  # Speed over ground from velocity magnitude
        "COG": round(np.degrees(v.heading) % 360, 3),  # Course over ground in degrees
        "Heading": round(np.degrees(v.heading) % 360, 3),  # Heading in degrees
        "VesselName": v.vehicle_type.upper(),  # Vehicle type as vessel name
        "VesselType": v.vehicle_type,  # Vehicle type
        "Length": round(getattr(v, 'scale', 0.0), 3),  # Using scale as length approximation
        "Width": round(getattr(v, 'scale', 0.0) / 3, 3),  # Approximate width as 1/3 of length
      })
    elif isinstance(v, Vehicle3D):
      data_rows_3d.append({
        "date": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[0] if settings.print_time_as == "iso" else "",
        "time": settings.current_simulation_time.isoformat(sep=",", timespec="seconds").split(",")[1] if settings.print_time_as == "iso" else settings.current_simulation_time.timestamp(),
        "icao_hex": f"{v.vehicle_id:06X}",  # ICAO hex from vehicle_id
        "latitude": round(v.latitude, 6),  # Latitude in degrees (~0.1m precision)
        "longitude": round(v.longitude, 6),  # Longitude in degrees (~0.1m precision)
        "altitude": round(v.pos_z, 3),  # Altitude in meters
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