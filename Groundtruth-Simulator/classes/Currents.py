from pathlib import Path
import xarray as xr
from .Vectors import Vector2D
import numpy as np

class Currents:
  def __init__(self):
    data_path = Path(__file__).resolve().parent / "ocean_currents.nc4"
    self.data = xr.open_dataset(data_path).squeeze("time", drop=True)

  def get_current(self, lat: float, lon: float) -> Vector2D:
    # Interpolate the current data to get the current at the given lat, lon, and time
    u = self.data["u_barotropic_velocity"].sel(lat=lat, lon=(lon+360)%360, method="nearest").values.item()
    v = self.data["v_barotropic_velocity"].sel(lat=lat, lon=(lon+360)%360, method="nearest").values.item()
    if np.isnan(u) or np.isnan(v):
      print(f"Warning: Current data is NaN at latitude={lat}, longitude={lon}. Returning zero current.")
      u = 0.0
      v = 0.0
    return Vector2D(u, v)

  def close(self):
    self.data.close()