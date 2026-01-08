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



def csv_print(filename: str = "JFN-Groudtruth-Simulator_result.csv"):
  """
  Docstring for csv_print
  """
  filename = _name_file(filename)
     

  with open(filename, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Column1", "Column2", "Column3"])
    writer.writerow([1, 2, 3])
    writer.writerow([4, 5, 6])