import csv
import time
from pathlib import Path
from classes import Vehicle2D, Vehicle3D

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
      fieldnames=[
        "vehicle_id",
        "time_stamp",
        "position_x",
        "position_y",
        "position_z",
      ],
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

  with open(filename, mode="a", newline="") as file:
    writer = csv.DictWriter(
      file,
      fieldnames=[
        "vehicle_id",
        "time_stamp",
        "position_x",
        "position_y",
        "position_z",
      ],
    )
    
    for vehicle in vehicles:
      if isinstance(vehicle, Vehicle2D):
        writer.writerow({
          "vehicle_id": vehicle.vehicle_id,
          "time_stamp": epoch_time,
          "position_x": vehicle.pos_x,
          "position_y": vehicle.pos_y,
          "position_z": 0.0,
        })
      elif isinstance(vehicle, Vehicle3D):
        writer.writerow({
          "vehicle_id": vehicle.vehicle_id,
          "time_stamp": epoch_time,
          "position_x": vehicle.pos_x,
          "position_y": vehicle.pos_y,
          "position_z": vehicle.pos_z,
        })