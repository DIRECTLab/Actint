
# JFN AIS Groundtruth Noiser

This project takes AIS position data in CSV form, simulates intermittent “visibility” (dropping some rows), applies random coordinate noise to the remaining latitude/longitude, and writes the resulting data back to CSV.

It is designed for quickly generating “noised” AIS tracks for experimentation.

## What it does

For each MMSI (vessel) in the input CSV:

1. Groups rows by `MMSI`.
2. Randomly decides whether each row is “visible” using the stateful process in [visible.py](visible.py).
3. Keeps only visible rows.
4. Sorts kept rows by `MMSI` then `BaseDateTime`.
5. Adds random noise (in meters) to `LAT` / `LON` using [noiser.py](noiser.py).
6. Writes outputs:
	 - One file per MMSI: `<MMSI>_sorted.csv`
	 - One combined file: `<input>_sorted.csv` (e.g. `2023-09-03_ais_top10_sorted.csv`)

Filename collisions are handled by [Next_available_filename.py](Next_available_filename.py): it will create `name (1).csv`, `name (2).csv`, etc.

## Requirements

- Python 3.10+ recommended
- Python packages:
	- `pandas`
	- `numpy`

## Usage

The main entry point is [main.py](main.py).

```powershell
python main.py [file] [noise_meter_lat] [noise_meter_lon] [visible_chance] [invisible_chance] [stay_visible_chance]
```

Example (use a larger noise radius):

```powershell
python main.py 2023-09-03_ais_top10.csv 250 250 0.95 0.80 0.80
```

### Arguments

All arguments are optional and are parsed independently: if one is missing or invalid, only that value falls back to its default.

| Position | Name | Type | Default | Meaning |
|---:|---|---|---:|---|
| 1 | `file` | string | `2023-09-03_ais_top10.csv` | Input AIS CSV path |
| 2 | `noise_meter_lat` | float | `100.0` | Max noise in meters applied to latitude |
| 3 | `noise_meter_lon` | float | `100.0` | Max noise in meters applied to longitude |
| 4 | `visible_chance` | float | `0.95` | If currently visible: probability it remains visible |
| 5 | `invisible_chance` | float | `0.80` | If currently invisible: probability it remains invisible |
| 6 | `stay_visible_chance` | float | `0.80` | Immediately after becoming visible again: probability it stays visible |

The script prints the parameter values it actually used on startup.

## Input CSV format

The script expects at minimum these columns:

- `MMSI`
- `BaseDateTime`
- `LAT`
- `LON`

It will carry through any other columns unchanged.

## Output files

Running the script will create:

- A combined file next to the input file: `<input_stem>_sorted<input_suffix>`
	- Example: `2023-09-03_ais_top10.csv` → `2023-09-03_ais_top10_sorted.csv`
- One file per MMSI in the repo root directory: `<MMSI>_sorted.csv`

All output rows have **noised** `LAT` and `LON`.

## How the noise works

The function `noise_coordinate(lat, lon, distance_m_lat, distance_m_lon)` in [noiser.py](noiser.py) adds a random offset in meters (uniformly sampled from `[-distance, +distance]`) and converts that offset into degree changes using a WGS84 earth radius approximation.

## How visibility works (important)

The `visible(...)` function in [visible.py](visible.py) uses module-level global state (`VISIBLE`, `FIRST_BACK`) to create “bursty” visibility/invisibility.

That means:

- Visibility is **stateful across calls**.
- In the current implementation, the same global state is used across *all* rows processed in a run (and across MMSI groups).

If you want visibility to be independent per vessel, you’d need to reset the state at the start of each `for name, group in groups:` loop (or refactor the logic into a per-vessel state object).

## Reproducibility (optional)

Both the visibility process and the noise use randomness.

If you want repeatable output, set both RNG seeds at the top of [main.py](main.py) before processing:

```python
import random
import numpy as np

random.seed(123)
np.random.seed(123)
```

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pandas'`**
	- Activate your venv and install dependencies: `pip install pandas numpy` for windows.
- **Outputs are being overwritten / clobbered**
	- They shouldn’t be: output naming goes through `next_available_filename(...)` which creates `(...).csv` variants when needed.

## Project layout

- [main.py](main.py): CLI script; reads input, filters by visibility, applies noise, writes output
- [visible.py](visible.py): stateful visibility/invisibility process
- [noiser.py](noiser.py): coordinate noising function
- [Next_available_filename.py](Next_available_filename.py): avoids overwriting existing outputs