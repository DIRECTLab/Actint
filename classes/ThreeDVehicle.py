import queue
from classes import TwoDVehicle, Position
import math

class ThreeDVehicle(TwoDVehicle):
    def __init__(self,
                 current_elevation: int,
                 max_elevation: int,
                 pitch_angle: float,

                 position: Position.Position3D,
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
        super().__init__(position,
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
        self.pitch_angle = pitch_angle # Degrees

        # Inherited from TwoDVehicle:
        # self.desired_heading = None # radians

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
        self._move_towards_destination()

    def _move_towards_destination(self):
        self._update_velocity()
        self._update_heading_and_pitch()
        self._move_forward()


    def _update_velocity(self):
        """
        Updates the vehicle's velocity the same way as the TwoDVehicle.
        """

        super()._update_velocity()

    def _update_heading_and_pitch(self):
        """
        Update both the heading and pitch angle to face the next destination.
        """
        self.position.get_heading(self.next_destination.position)

        
        
        # Update heading using the TwoDVehicle method
        super()._update_heading()

    def _move_forward(self):
        self.current_elevation += self.current_velocity * math.sin(math.radians(self.pitch_angle))
        if self.current_elevation > self.max_elevation:
            self.current_elevation = self.max_elevation
            self.pitch_angle = 0