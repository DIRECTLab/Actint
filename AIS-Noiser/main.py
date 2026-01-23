from pathlib import Path
import pandas as pd
import sys
from visible import visible
from Next_available_filename import next_available_filename
from noiser import noise_coordinate, noise_time

def main():
  """
  Main function to read AIS data from a CSV file, apply visibility filtering and coordinate noise, and write the results to new CSV files. This 

  :param file: Path to the input CSV file.
  :type file: str 
  :param noise_meter_lat: Maximum noise distance in meters for latitude.
  :type noise_meter_lat: float
  :param noise_meter_lon: Maximum noise distance in meters for longitude.
  :type noise_meter_lon: float
  :param noise_time_seconds: Maximum noise to add or subtract in seconds.
  :type noise_time_seconds: float
  :param visible_chance: Chance that a visible object remains visible.
  :type visible_chance: float from 0-1
  :param invisible_chance: Chance that an invisible object remains invisible.
  :type invisible_chance: float from 0-1
  :param stay_visible_chance: Chance that an object that has just become visible remains visible.
  :type stay_visible_chance: float from 0-1
  """
  def argv_or_default(index: int, cast, default):
    try:
      return cast(sys.argv[index])
    except (IndexError, ValueError):
      return default

  file = argv_or_default(1, str, '2023-09-03_ais_top10.csv')
  noise_meter_lat = argv_or_default(2, float, 100.0)
  noise_meter_lon = argv_or_default(3, float, 100.0)
  noise_time_seconds = argv_or_default(4, float, 20.0)
  visible_chance = argv_or_default(5, float, 0.95)
  invisible_chance = argv_or_default(6, float, 0.80)
  stay_visible_chance = argv_or_default(7, float, 0.80)

  # Optional: show what parameters actually got used.
  print(f"Using parameters: file={file}, noise_meter_lat={noise_meter_lat}, noise_meter_lon={noise_meter_lon}")
  print(f"noise_time_seconds={noise_time_seconds}")
  print(f"visible_chance={visible_chance}, invisible_chance={invisible_chance}, stay_visible_chance={stay_visible_chance}")
  
  data = pd.read_csv(filepath_or_buffer=file, header=0)
  groups = data.groupby(by='MMSI')

  input_path = Path(file)
  sorted_outfile = next_available_filename(input_path.with_name(f"{input_path.stem}_noised{input_path.suffix}"))
  data[0:0].to_csv(sorted_outfile, index=False)


  for name, group in groups:
    outfile = next_available_filename(f"{name}_noised.csv")

    # 1) Write only the header to a fresh output file.
    group.iloc[0:0].to_csv(outfile, index=False)

    # 2) Append only rows that meet the external requirements.
    passing_indices = []
    for idx, row in group.iterrows():
      if visible(visible_chance, invisible_chance, stay_visible_chance):
        passing_indices.append(idx)

    if passing_indices:
      out_df = group.loc[passing_indices].sort_values(by=['MMSI', 'BaseDateTime']).copy()

      # Apply coordinate noise row-by-row and write the edited rows.
      for idx, row in out_df.iterrows():
        new_lat, new_lon = noise_coordinate(
          float(row['LAT']),
          float(row['LON']),
          noise_meter_lat,
          noise_meter_lon,
        )
        out_df.at[idx, 'LAT'] = new_lat
        out_df.at[idx, 'LON'] = new_lon

      # Apply time-stamp noise row-by-row and write the edited rows.
      for idx, row in out_df.iterrows():
        new_time = noise_time(row['BaseDateTime'], noise_time_seconds)
        out_df.at[idx, 'BaseDateTime'] = new_time

      out_df.to_csv(outfile, mode='a', header=False, index=False)
      out_df.to_csv(sorted_outfile, mode='a', header=False, index=False)



if __name__ == "__main__":
    main()