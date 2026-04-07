import sys
import matplotlib
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")


def wrap_lon_180(lon_degrees: np.ndarray) -> np.ndarray:
  """Wrap longitude(s) into [-180, 180)."""
  lon_degrees = np.asarray(lon_degrees, dtype=float)
  return ((lon_degrees + 180.0) % 360.0) - 180.0


def insert_penup_gaps(lon: np.ndarray, lat: np.ndarray, *, jump_degrees: float = 180.0):
  """Insert NaN gaps where lon jumps across the dateline.

  Matplotlib breaks a line at NaNs, which mimics "picking up the pen".
  """
  lon = np.asarray(lon, dtype=float)
  lat = np.asarray(lat, dtype=float)
  if lon.size != lat.size:
    raise ValueError("lon and lat must have the same length")
  if lon.size < 2:
    return lon, lat

  breaks = np.where(np.abs(np.diff(lon)) > jump_degrees)[0] + 1
  if breaks.size == 0:
    return lon, lat

  return np.insert(lon, breaks, np.nan), np.insert(lat, breaks, np.nan)


def non_clobber_png_path(output_path: str) -> str:
  """Return a filename that won't overwrite an existing file.

  Example: plot.png -> plot_1.png -> plot_2.png ...
  """
  path = Path(output_path)

  # If caller provided only a filename, force it into ./output
  if path.parent == Path("."):
    path = Path("output") / path

  if path.suffix.lower() != ".png":
    path = path.with_suffix(".png")

  if not path.exists():
    return str(path)

  for i in range(1, 10_000):
    candidate = path.with_name(f"{path.stem}_{i}{path.suffix}")
    if not candidate.exists():
      return str(candidate)

  raise RuntimeError(f"Could not find a free filename for {output_path}")

def main():
  csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "plotter_data.csv")
  if len(sys.argv) == 1:
    print("No CSV file specified, using default 'plotter_data.csv'")

  df = pd.read_csv(csv_path)

  required_cols = {"MMSI", "LAT", "LON"}
  missing = required_cols - set(df.columns)
  if missing:
    raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}")

  df = df.dropna(subset=["MMSI", "LAT", "LON"]).copy()
  df["MMSI"] = df["MMSI"].astype(str)

  if "BaseDateTime" in df.columns:
    df = df.sort_values(["MMSI", "BaseDateTime"])

  fig, ax = plt.subplots(figsize=(8, 6))
  mmsi_values = sorted(df["MMSI"].unique())
  cmap = plt.get_cmap("tab20", max(1, len(mmsi_values)))

  for idx, mmsi in enumerate(mmsi_values):
    g = df[df["MMSI"] == mmsi]
    lon = wrap_lon_180(g["LON"].to_numpy(dtype=float))
    lat = g["LAT"].to_numpy(dtype=float)
    lon, lat = insert_penup_gaps(lon, lat, jump_degrees=180.0)
    ax.plot(lon, lat, label=mmsi, color=cmap(idx), linewidth=1.5)
    # ax.scatter(g["LON"], g["LAT"], label=mmsi, color=cmap(idx), s=10)


  ax.set_title(csv_path.name)
  ax.set_xlabel("Longitude (degrees)")
  ax.set_ylabel("Latitude (degrees)")
  ax.grid(True, alpha=0.3)
  ax.set_aspect("equal", adjustable="datalim")
  ax.legend(title="MMSI", loc="best")
  fig.tight_layout()
  output_path = non_clobber_png_path(f"{csv_path.stem}.png")
  Path(output_path).parent.mkdir(parents=True, exist_ok=True)
  fig.savefig(output_path, dpi=300, bbox_inches="tight")
  plt.close(fig)
  print(f"Saved plot to: {output_path}")
  
if __name__== "__main__":
    main()
