import csv
import math
import time
from datetime import datetime
from pathlib import Path
from classes import Vehicle2D, Vehicle3D


def _ais_fieldnames() -> list[str]:
  # Matches the header row in AIS-Noiser/2023-09-03_ais_top10.csv
  return [
    "Unnamed: 0",
    "MMSI",
    "BaseDateTime",
    "LAT",
    "LON",
    "SOG",
    "COG",
    "Heading",
    "VesselName",
    "IMO",
    "CallSign",
    "VesselType",
    "Status",
    "Length",
    "Width",
    "Draft",
    "Cargo",
    "TransceiverClass",
  ]


def _existing_data_row_count(filename: str) -> int:
  """Return how many data rows exist (excludes the header)."""
  try:
    with open(filename, mode="r", newline="") as f:
      # -1 to discount the header line.
      return max(sum(1 for _ in f) - 1, 0)
  except FileNotFoundError:
    return 0

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

def csv_print_header(file: str) -> str:
  """Create a new CSV file with headers for vehicle simulation data.
  
  Creates a CSV file named "JFN-Groudtruth-Simulator_result.csv" (or an
  incremented version if the file exists). The file contains headers for:
  vehicle_id, time_stamp, and position (x/y/z).
  
  Returns:
    The name of the created CSV file as a string.
  """
  filename =_name_file(file).name
  with open(filename, mode="w", newline="") as f:
    writer = csv.DictWriter(
      f,
      fieldnames=_ais_fieldnames(),
    )
    writer.writeheader()

  return filename

def csv_print_data(vehicles: list, filename: str) -> None:
  """Append vehicle data to an existing CSV file.
  
  Extracts position from each vehicle and writes it as rows in the specified CSV file.
  Supports Vehicle2D and Vehicle3D.
  For 2D vehicles, z-axis values are set to 0.0.
  
  Args:
    vehicles: List of vehicle objects (currently supports Vehicle2D instances).
    filename: Path to the CSV file where data should be appended.
  
  Note:
    The file must already exist with the proper headers (use csv_print_header first).
  """

  # Unix epoch timestamp (seconds) for this batch write.
  epoch_time = time.time()
  base_datetime = datetime.utcfromtimestamp(epoch_time).strftime("%Y-%m-%d %H:%M:%S")

  start_index = _existing_data_row_count(filename)

  with open(filename, mode="a", newline="") as out_file:
    writer = csv.DictWriter(out_file, fieldnames=_ais_fieldnames())

    row_index = start_index

    for vehicle in vehicles:
      if not isinstance(vehicle, (Vehicle2D, Vehicle3D)):
        continue

      # Map simulator coordinates to AIS-like LAT/LON.
      # Convention used here: pos_y -> LAT, pos_x -> LON.
      lat = float(vehicle.pos_y)
      lon = float(vehicle.pos_x)

      # Compute SOG/COG from the current velocity if available.
      try:
        vx = float(vehicle.velocity_x)
        vy = float(vehicle.velocity_y)
      except Exception:
        vx = 0.0
        vy = 0.0

      speed_mps = math.hypot(vx, vy)
      sog_knots = speed_mps * 1.9438444924406048

      if speed_mps > 1e-9:
        # Maritime convention: 0° = north, clockwise.
        angle = math.atan2(vy, vx)
        heading_rad = (math.pi / 2 - angle) % (2 * math.pi)
        cog_deg = math.degrees(heading_rad)
        heading_deg = float(int(round(cog_deg)) % 360)
      else:
        cog_deg = 0.0
        heading_deg = 511.0  # AIS "not available" heading

      mmsi = int(vehicle.vehicle_id)
      writer.writerow(
        {
          "Unnamed: 0": row_index,
          "MMSI": mmsi,
          "BaseDateTime": base_datetime,
          "LAT": lat,
          "LON": lon,
          "SOG": round(sog_knots, 1),
          "COG": round(cog_deg, 1),
          "Heading": heading_deg,
          "VesselName": f"SIM_{mmsi}",
          "IMO": "",
          "CallSign": "",
          "VesselType": 0.0,
          "Status": 0.0,
          "Length": 0.0,
          "Width": 0.0,
          "Draft": "",
          "Cargo": 0.0,
          "TransceiverClass": "A",
        }
      )

      row_index += 1