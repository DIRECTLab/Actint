import csv
from pathlib import Path

def _name_file(file: str) -> Path:
  """Return True if a file with the given name exists in search_dir."""
  path = Path(file)
  stem = path.stem
  suffix = path.suffix

  counter = 0
  new_path = path
  while new_path.exists():
    counter += 1
    new_path = path.with_name(f"{stem}_{counter}{suffix}")

  return new_path



def csv_print(vehicles: list, name: str = "JFN-Groudtruth-Simulator_result.csv") -> None:
  """
  Takes list of vehicles and prints their data to a CSV file. Default filename is "JFN-Groudtruth-Simulator_result_0.csv" with 0 being incremented to the next available number to avoid overwriting previous runs.
  """
  filename = _name_file(name)
     

  with open(filename, mode="w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=["vehicle_id", "time_stamp", "position_x", "position_y", "position_z", "velocity_x", "velocity_y", "velocity_z", "acceleration_x", "acceleration_y", "acceleration_z", "heading", "action"])
    writer.writeheader()