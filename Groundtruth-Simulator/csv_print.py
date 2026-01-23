import pandas as pd
import numpy as np
import datetime
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
  
  Creates a CSV file matching AIS data format with available simulation fields.
  
  Returns:
    The name of the created CSV file as a string.
  """
  filename = _name_file(file).name
  
  # Create an empty DataFrame with AIS-like column headers
  df = pd.DataFrame(columns=[
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
  
  # Write the DataFrame to CSV with index as row number
  df.to_csv(filename, index=True, index_label="Unnamed: 0")

  return filename

def csv_print_data(vehicles: list, filename: str) -> None:
  """Append vehicle data to an existing CSV file in AIS format.
  
  Extracts vehicle data and writes it in AIS-like format.
  Supports Vehicle2D and Vehicle3D.
  
  Args:
    vehicles: List of vehicle objects.
    filename: Path to the CSV file where data should be appended.
  
  Note:
    The file must already exist with proper headers (use csv_print_header first).
  """

  epoch_time = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')

  # Calculate speed and convert heading to degrees
  data_rows = [
    {
      "MMSI": v.vehicle_id,
      "BaseDateTime": epoch_time,
      "LAT": float(v.pos_y),  # Using y as latitude
      "LON": float(v.pos_x),  # Using x as longitude
      "SOG": round(np.linalg.norm(v.velocity.vector), 3),  # Speed over ground from velocity magnitude
      "COG": round(np.degrees(v.heading) % 360, 3),  # Course over ground in degrees
      "Heading": round(np.degrees(v.heading) % 360, 3),  # Heading in degrees
      "VesselName": v.vehicle_type.upper(),  # Vehicle type as vessel name
      "VesselType": v.vehicle_type,  # Vehicle type
      "Length": round(getattr(v, 'scale', 0.0), 3),  # Using scale as length approximation
      "Width": round(getattr(v, 'scale', 0.0) / 3, 3),  # Approximate width as 1/3 of length
    }
    for v in vehicles
  ]
  
  # Create DataFrame and append with row index
  df = pd.DataFrame(data_rows)
  # Get the current number of rows in the file to continue indexing
  try:
    existing_df = pd.read_csv(filename)
    start_index = len(existing_df) + 1
  except (FileNotFoundError, pd.errors.EmptyDataError):
    start_index = 1
  
  df.index = range(start_index, start_index + len(df))
  df.to_csv(filename, mode='a', header=False, index=True)
