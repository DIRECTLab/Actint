from pathlib import Path
from Settings import Settings
import sys
import os


def _output_dir() -> Path:
  if Path("/.dockerenv").exists() and Path("/app/output").exists():
    outdir = Path("/app/output")
  else:
    repo_root = Path(__file__).resolve().parents[1]
    outdir = repo_root / "output" / "ais-noiser"

  outdir.mkdir(parents=True, exist_ok=True)
  return outdir

def next_available_filename(base):
  """
  Find the next available filename by appending (1), (2), etc. before the file extension.
  
  :param base: file path to start from
  """
  outdir = _output_dir()
  target = outdir / Path(base).name

  if not target.exists():
    return str(target)

  for i in range(1, 10_000):
    candidate = target.with_name(f"{target.stem} ({i}){target.suffix}")
    if not candidate.exists():
      return str(candidate)

  raise RuntimeError(f"Could not find a free filename for {target}")

def parse_input() -> Settings:
  if '--help' in sys.argv or '-h' in sys.argv:
    print("Usage: python main.py [--file FILE] [--latnoise METERS] [--lonnoise METERS] [--altnoise METERS] [--timenoise SECONDS] [--visible CHANCE] [--invisible CHANCE] [--stayvisible CHANCE] [-3d] [-2d] [-t]")
    print("Example: python main.py -2d --file 2023-09-03_ais_top10.csv --latnoise 100.0 --lonnoise 100.0 --altnoise 50.0 --timenoise 20.0 --visible 0.95 --invisible 0.80 --stayvisible 0.80 -t")
    print("Flags:")
    print("  -t               Allow time noise to be added both forward and backward.")
    print("  -3d              Process data as 3D (with altitude in ADS-B form).")
    print("  -2d              Process data as 2D (without altitude in AIS form).")
    sys.exit(0)

  def get_flag_value(flag, cast, default):
    """Get the value following a flag in sys.argv"""
    try:
      idx = sys.argv.index(flag)
      return cast(sys.argv[idx + 1])
    except (ValueError, IndexError):
      return default

  time_backward = False
  twod = True

  if '-t' in sys.argv:
    time_backward = True

  if '-3d' in sys.argv:
    twod = False

  if '-2d' in sys.argv:
    twod = True

  return Settings(
    file = get_flag_value('--file', str, '2023-09-03_ais_top10.csv'),
    noise_lat = get_flag_value('--latnoise', float, 100.0),
    noise_lon = get_flag_value('--lonnoise', float, 100.0),
    noise_alt = get_flag_value('--altnoise', float, 50.0),
    noise_time = get_flag_value('--timenoise', float, 20.0),
    visible_chance = get_flag_value('--visible', float, 0.95),
    invisible_chance = get_flag_value('--invisible', float, 0.80),
    stay_visible_chance = get_flag_value('--stayvisible', float, 0.80),
    time_backward = time_backward,
    twod = twod,
  )
