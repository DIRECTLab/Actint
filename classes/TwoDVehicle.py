from queue import Queue
from classes import Vehicle
import math

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
                         time_step,
                         )
        self.position_x = position_x # Longitude
        self.position_y = position_y # Latitude
        self.current_velocity = current_velocity # Km/h
        self.max_velocity = max_velocity # Km/h
        self.max_acceleration = max_acceleration # m/s^2
        self.heading = heading # radians
        self.desired_heading = None # radians
        self.max_heading_delta = max_heading_delta # radians/second


    def update(self):
        """
        Update the vehicle's position and state. Does nothing is there is no current or next destination.
        """
        # If there isn't a current destination and no more destinations, do nothing
        if self.next_destination is None and self._has_next_destination() is False:
            return
        # If there isn't a current destination but there are more destinations, assign one
        if self.next_destination is None and self._has_next_destination() is True:
            self._assign_next_destination()
            self._update_desired_heading()
        # If we are at the current destination, assign the next one
        if self._is_at_destination():
            self._assign_next_destination()
            self._update_desired_heading()
        # If there is a current destination, move towards it
        self._move_towards_destination()
    

    def _is_at_destination(self) -> bool:
        """
        Check if the vehicle is at its next destination within the allowed error margin.
        
        Returns True if at destination, otherwise False.
        """
        if abs(self.position_x - self.next_destination.position_x) <= self.next_destination.error:
            if abs(self.position_y - self.next_destination.position_y) <= self.next_destination.error:
                return True
        return False
    

    def _update_desired_heading(self):
  
        return


    def _move_towards_destination(self):
        self._move_forward()
        self._update_velocity()
        self._update_heading()

    def _move_forward(self):
        self.position_x += math.cos(self.heading) * self.current_velocity * (self.time_step / 3600)
        self.position_y += math.sin(self.heading) * self.current_velocity * (self.time_step / 3600)
        return
    
    def _update_velocity(self):
        # If current velocity is equal to target speed, do nothing
        if self.current_velocity == self.next_destination.target_speed_to_next_destination:
            return
        # If current velocity is less than target speed, accelerate
        elif self.current_velocity < self.next_destination.target_speed_to_next_destination:
            self.current_velocity += self.max_acceleration * (self.time_step / 3600)
        # If current velocity is greater than target speed, decelerate
        elif self.current_velocity > self.next_destination.target_speed_to_next_destination:
            self.current_velocity -= self.max_acceleration * (self.time_step / 3600)
        # Ensure velocity does not exceed max velocity
        if self.current_velocity > self.max_velocity:
            self.current_velocity = self.max_velocity

    def _update_heading(self):

        pass
