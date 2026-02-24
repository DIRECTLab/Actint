from pathlib import Path
import pandas as pd
import sys
from visible import visible
from helper_functions import next_available_filename, parse_input
from noiser import noise_coordinate, noise_time

def main():
  """
  Main function to read AIS data from a CSV file, apply visibility filtering and coordinate noise, and write the results to new CSV files. Takes command-line arguments for configuration.

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

  settings = parse_input()

  # Optional: show what parameters actually got used.
  print(settings)

  def ais():
    data = pd.read_csv(filepath_or_buffer=settings.file, header=0)
    groups = data.groupby(by='MMSI')

    input_path = Path(settings.file)
    sorted_outfile = next_available_filename(input_path.with_name(f"{input_path.stem}_noised{input_path.suffix}"))
    data[0:0].to_csv(sorted_outfile, index=False)


    for name, group in groups:
      outfile = next_available_filename(f"{name}_noised.csv")

      # 1) Write only the header to a fresh output file.
      group.iloc[0:0].to_csv(outfile, index=False)

      # 2) Append only rows that meet the external requirements.
      passing_indices = []
      for idx, row in group.iterrows():
        if visible(settings.visible_chance, settings.invisible_chance, settings.stay_visible_chance):
          passing_indices.append(idx)

      if passing_indices:
        out_df = group.loc[passing_indices].sort_values(by=['MMSI', 'BaseDateTime']).copy()

        # Apply coordinate noise row-by-row and write the edited rows.
        for idx, row in out_df.iterrows():
          new_lat, new_lon = noise_coordinate(
            float(row['LAT']),
            float(row['LON']),
            settings.noise_lat,
            settings.noise_lon,
          )
          out_df.at[idx, 'LAT'] = new_lat
          out_df.at[idx, 'LON'] = new_lon

        # Apply time-stamp noise row-by-row and write the edited rows.
        for idx, row in out_df.iterrows():
          new_time = noise_time(datetime=row['BaseDateTime'], settings=settings)
          out_df.at[idx, 'BaseDateTime'] = new_time

        out_df.to_csv(outfile, mode='a', header=False, index=False)
        out_df.to_csv(sorted_outfile, mode='a', header=False, index=False)

  def adsb():
    data = pd.read_csv(filepath_or_buffer=settings.file, header=0, dtype={'icao_hex': str})
    groups = data.groupby(by='icao_hex')

    input_path = Path(settings.file)
    sorted_outfile = next_available_filename(input_path.with_name(f"{input_path.stem}_noised{input_path.suffix}"))
    data[0:0].to_csv(sorted_outfile, index=False)

    for name, group in groups:
      outfile = next_available_filename(f"{name}_noised.csv")

      # 1) Write only the header to a fresh output file.
      group.iloc[0:0].to_csv(outfile, index=False)

      # 2) Append only rows that meet the external requirements.
      passing_indices = []
      for idx, row in group.iterrows():
        if visible(settings.visible_chance, settings.invisible_chance, settings.stay_visible_chance):
          passing_indices.append(idx)

      if passing_indices:
        out_df = group.loc[passing_indices].sort_values(by=['icao_hex', 'date', 'time']).copy()

        # Apply coordinate noise row-by-row and write the edited rows.
        for idx, row in out_df.iterrows():
          new_lat, new_lon, new_alt = noise_coordinate(
            float(row['latitude']),
            float(row['longitude']),
            settings.noise_lat,
            settings.noise_lon,
            float(row['altitude']),
            settings.noise_alt,
            is_2d = False,
          )
          out_df.at[idx, 'latitude'] = new_lat
          out_df.at[idx, 'longitude'] = new_lon
          out_df.at[idx, 'altitude'] = new_alt

        # Apply time-stamp noise row-by-row and write the edited rows.
        for idx, row in out_df.iterrows():
          new_time = noise_time(time=row['time'], date=row['date'], settings=settings)

          out_df.at[idx, 'time'] = new_time.split(' ')[1]
          out_df.at[idx, 'date'] = new_time.split(' ')[0]

        out_df.to_csv(outfile, mode='a', header=False, index=False)
        out_df.to_csv(sorted_outfile, mode='a', header=False, index=False)

  if settings.twod:
    ais()
  else:
    adsb()

if __name__ == "__main__":
    main()