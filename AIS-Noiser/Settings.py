class Settings ():
  def __init__(self, noise_lat: float, noise_lon: float, noise_alt: float, noise_time: float, visible_chance: float, invisible_chance: float, stay_visible_chance: float, file: str, time_backward: bool, twod: bool):
    self.noise_lat = noise_lat
    self.noise_lon = noise_lon
    self.noise_alt = noise_alt
    self.noise_time = noise_time
    self.visible_chance = visible_chance
    self.invisible_chance = invisible_chance
    self.stay_visible_chance = stay_visible_chance
    self.file = file
    self.noise_time_backward = time_backward
    self.twod = twod

  def __str__(self):
    string = f""
    if self.twod:
      string += "Noising 2D data in AIS-Noiser. "
    else:
      string += "Noising 3D data in ADS-B-Noiser. "
    string += f"File: {self.file}, Lat Noise: {self.noise_lat}m, Lon Noise: {self.noise_lon}m, "
    if not self.twod:
      string += f"Alt Noise: {self.noise_alt}m, "
    string += f"Time Noise: {self.noise_time}s, "
    string += f"Visible Chance: {self.visible_chance}, Invisible Chance: {self.invisible_chance}, Stay Visible Chance: {self.stay_visible_chance}, "
    if self.noise_time_backward:
      string += "Time noise can be both forward and backward."
    else:
      string += "Time noise is only forward, "

    return string