from datetime import datetime as dt, timedelta


class Settings:
    def __init__(self, default_time_step: float = 0.4, latlon_origin: dict = None) -> None:
        self.default_time_step = default_time_step  # Default time step in seconds
        self.latlon_origin = latlon_origin or {
            "latitude": 20.590305,   # ~20.59°N latitude
            "longitude": -157.697742,  # ~157.70°W longitude
            "height": 0.0              # Sea level
        }
        self.current_simulation_time = dt.now()  # Initialize current simulation time

    def advance_time(self, time_step: float) -> None:
        """Advance the current simulation time by the given time step in seconds."""
        self.current_simulation_time += timedelta(seconds=time_step)