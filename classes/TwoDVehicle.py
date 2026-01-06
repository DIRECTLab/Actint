import queue
from classes import Vehicle, Position
import math

class TwoDVehicle(Vehicle):
    def __init__(self,
                 position: Position.Position2D,
                 current_velocity: float,
                 max_velocity: float,
                 max_acceleration: float,
                 heading: float,
                 max_heading_delta: float,

                 vehicle_type: str,
                 vehicle_id: int,
                 destination_queue: queue.Queue,
                 time_step: int,
                 ):
        super().__init__(vehicle_type,
                         vehicle_id,
                         destination_queue,
                         time_step,
                         )
        self.position = position
        self.current_velocity = current_velocity # Km/h
        self.max_velocity = max_velocity # Km/h
        self.max_acceleration = max_acceleration # m/s^2
        self.heading = heading # radians
        self.desired_heading = None # radians
        self.max_heading_delta = max_heading_delta # radians/second
        # Inherited from Vehicle:
        # self.vehicle_type = vehicle_type
        # self.vehicle_id = vehicle_id
        # self.time_step = time_step
        # self.destination_queue = destination_queue
        # self.next_destination: Destination = None


    def update(self):
        """
        Update the vehicle's position and state. Does nothing if there is no current or next destination.
        """
        # If there isn't a current destination and no more destinations, do nothing
        if self.next_destination is None and self._has_next_destination() is False:
            return
        # If there isn't a current destination but there are more destinations, assign one
        if self.next_destination is None and self._has_next_destination() is True:
            self._assign_next_destination()
        # If we are at the current destination, assign the next one
        if self.next_destination.has_reached(self.position):
            self._assign_next_destination()
        # If there is a current destination, move towards it
        if self._has_next_destination():
            self._seek()
        else:
            self._arrive()
    

    def _seek(self):
        pass


    def _arrive(self):
        pass