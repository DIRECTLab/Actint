from queue import Queue
from classes import Vehicle

class TwoDVehicle(Vehicle):
    def __init__(self,
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
        super().__init__(vehicle_type,
                         vehicle_id,
                         destination_queue,
                         time_step)
        self.position_x = position_x
        self.position_y = position_y
        self.current_velocity = current_velocity
        self.max_velocity = max_velocity
        self.max_acceleration = max_acceleration
        self.heading = heading
        self.max_heading_delta = max_heading_delta


    def update(self):
        pass