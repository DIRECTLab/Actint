import queue
from .Vehicle2D import Vehicle2D
from .Position import Position3D
import math
import numpy as np

# Helper functions adapted to use Position3D
def normalize(v: Position3D) -> Position3D:
    v_vec = v.vector
    norm = np.linalg.norm(v_vec)
    if norm > 1e-9:
        return Position3D(*[float(x) for x in v_vec / norm])
    return Position3D(0.0, 0.0, 0.0)

def truncate(v: Position3D, limit: float) -> Position3D:
    v_vec = v.vector
    norm = np.linalg.norm(v_vec)
    if norm > limit:
        return Position3D(*[float(x) for x in v_vec * (limit / norm)])
    return v

def scale_position(pos: Position3D, scalar: float) -> Position3D:
    """Scale a position vector by a scalar."""
    return Position3D(pos.x * scalar, pos.y * scalar, pos.z * scalar)

class Vehicle3D(Vehicle2D):
    def __init__(self,
                 current_elevation: int,
                 max_elevation: int,
                 pitch_angle: float,
                 position: Position3D,
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
        self.pitch_angle = pitch_angle

    @property
    def pos_z(self) -> float:
        return self.position.z
    
    @pos_z.setter
    def pos_z(self, value: float) -> None:
        self.position.z = value

    @property
    def velocity_z(self) -> float:
        return self._velocity.z
    
    @velocity_z.setter
    def velocity_z(self, value: float) -> None:
        self._velocity.z = value

    @property
    def acceleration_z(self) -> float:
        return self._acceleration.z
    
    

    def seek(self) -> Position3D:
        """Calculate steering force towards target in 3D space."""
        desired_direction = self.position.get_direction_vector(self.target)
        desired_velocity = scale_position(desired_direction, self.max_speed)
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def flee(self) -> Position3D:
        """Calculate steering force away from target in 3D space."""
        desired_direction = self.position.get_direction_vector(self.target)
        desired_velocity = scale_position(desired_direction, -self.max_speed)
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def arrive(self) -> Position3D:
        """Calculate steering force to arrive smoothly at target in 3D space."""
        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)
        if distance < 1:
            return Position3D(0.0, 0.0, 0.0)
        desired_direction = self.position.get_direction_vector(self.target)
        speed = min(distance / 0.3, self.max_speed)
        desired_velocity = scale_position(desired_direction, speed)
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def update(self, dt: float, window_w: int, window_h: int) -> None:
        """Update vehicle position and state."""
        if self.next_destination is None:
            if not self._has_next_destination():
                return
            self._assign_next_destination()
        elif self.next_destination.has_reached(self.position):
            self._assign_next_destination()
        distance_to_target = self.position.distance_to(self.target)
        if self.action == 'seek':
            self._acceleration = self.seek()
        elif self.action == 'flee':
            self._acceleration = self.flee() if distance_to_target < 300 else Position3D(0.0, 0.0, 0.0)
        elif self.action == 'arrive':
            self._acceleration = self.arrive()
        else:
            self._acceleration = Position3D(0.0, 0.0, 0.0)
        self._velocity = truncate(self._velocity + scale_position(self._acceleration, dt), self.max_speed)
        self.position = self.position + scale_position(self._velocity, dt)
        if self._velocity.distance_to(Position3D(0, 0, 0)) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)
            h_mag = math.sqrt(direction.x**2 + direction.y**2)
            self.pitch_angle = math.degrees(math.atan2(direction.z, h_mag))
        self.position.x = self.position.x % window_w
        self.position.y = self.position.y % window_h
        self.position.z = max(0, min(self.position.z, self.max_elevation))