import sys
import matplotlib
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

matplotlib.use("Agg")


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
  csv_path = sys.argv[1] if len(sys.argv) > 1 else "plotter_data.csv"
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
    ax.plot(g["LON"], g["LAT"], label=mmsi, color=cmap(idx), linewidth=1.5)

  ax.set_title(csv_path)
  ax.set_xlabel("LON")
  ax.set_ylabel("LAT")
  ax.grid(True, alpha=0.3)
  ax.set_aspect("equal", adjustable="datalim")
  ax.legend(title="MMSI", loc="best")
  fig.tight_layout()
  output_path = non_clobber_png_path("plot.png")
  Path(output_path).parent.mkdir(parents=True, exist_ok=True)
  fig.savefig(output_path, dpi=300, bbox_inches="tight")
  plt.close(fig)
  print(f"Saved plot to: {output_path}")
  
if __name__== "__main__":
    main()