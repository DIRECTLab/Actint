import xarray as xr
from .Position import Position2D

class Currents:
  def __init__(self):
    self.data = xr.open_dataset("classes/ocean_currents.nc4").squeeze("time", drop=True)

  def get_current(self, lat: float, lon: float) -> Position2D:
    # Interpolate the current data to get the current at the given lat, lon, and time
    u = self.data["u_barotropic_velocity"].sel(lat=(lat+360)%360, lon=lon, method="nearest").values.item()
    v = self.data["v_barotropic_velocity"].sel(lat=(lat+360)%360, lon=lon, method="nearest").values.item()
    return Position2D(u, v)

  def close(self):
    self.data.close()