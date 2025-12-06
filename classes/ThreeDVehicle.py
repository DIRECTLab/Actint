from queue import Queue
from classes import TwoDVehicle

class ThreeDVehicle(TwoDVehicle):
    def __init__(self,
                 current_elevation: int,
                 max_elevation: int,
                 pitch_angle: float,

                 position_x: float,
                 position_y: float,
                 current_velocity: float,
                 max_velocity: float,
                 max_acceleration: float,
                 heading: float,
                 max_heading_delta: float,

                 vehicle_type: str,
                 vehicle_id: int,
                 destination_queue: Queue,
                 time_step: int,
                 ):
        super().__init__(position_x,
                         position_y,
                         current_velocity,
                         max_velocity,
                         max_acceleration,
                         heading,
                         max_heading_delta,

                         vehicle_type,
                         vehicle_id,
                         destination_queue,
                         time_step)
        self.current_elevation = current_elevation
        self.max_elevation = max_elevation
        self.pitch_angle = pitch_angle

    def update(self):
        pass