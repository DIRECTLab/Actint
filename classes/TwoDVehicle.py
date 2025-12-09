from queue import Queue
from classes import Vehicle, Position
import math

class TwoDVehicle(Vehicle):
    def __init__(self,
                 position: Position,
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
        self.position = position
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
        # If we are at the current destination, assign the next one
        if self.next_destination.has_reached(self.position):
            self._assign_next_destination()
        # If there is a current destination, move towards it
        self._move_towards_destination()
    

    def _move_towards_destination(self):
        self._update_velocity()
        self._update_heading()
        self._move_forward()

    def _move_forward(self):
        # Convert velocity from km/h to km/s, then multiply by time_step in seconds
        # km/h ÷ 3600 = km/s, then × seconds = km traveled
        max_distance = self.current_velocity * (self.time_step / 3600)
        self.position.x += math.cos(self.heading) * max_distance
        self.position.y += math.sin(self.heading) * max_distance
        return
    
    def _update_velocity(self):
        if self.current_velocity == self.next_destination.target_speed_to_next_destination:
            return
        
        max_velocity_change = self.max_acceleration * 3600/1000 * self.time_step
        # If current velocity is less than target speed, accelerate
        if self.current_velocity < self.next_destination.target_speed_to_next_destination:
            self.current_velocity += min(max_velocity_change, self.next_destination.target_speed_to_next_destination - self.current_velocity)
        # If current velocity is greater than target speed, decelerate
        elif self.current_velocity > self.next_destination.target_speed_to_next_destination:
            self.current_velocity -= min(max_velocity_change, self.current_velocity - self.next_destination.target_speed_to_next_destination)
        # Ensure velocity does not exceed max velocity
        if self.current_velocity > self.max_velocity:
            self.current_velocity = self.max_velocity

    def _update_heading(self):
        # Calculate desired heading towards destination
        delta_x = self.next_destination.position_x - self.position_x
        delta_y = self.next_destination.position_y - self.position_y
        desired_heading = math.atan2(delta_y, delta_x)

        if desired_heading == self.heading:
            return
        # Adjust heading gradually: max_heading_delta (rad/s) × time_step (s) = max radians to turn
        if desired_heading < self.heading:
            self.heading -= min(self.max_heading_delta * self.time_step, self.heading - desired_heading)
        elif desired_heading > self.heading:
            self.heading += min(self.max_heading_delta * self.time_step, desired_heading - self.heading)
        pass
