import queue, math
import numpy as np
from numpy.typing import NDArray
from .Vehicle import Vehicle
from .Position import Position3D


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

class Vehicle3D(Vehicle):
    def __init__(
            self,
            vehicle_type: str,
            vehicle_id: int,
            destination_queue: queue.Queue,
            time_step: float,

            position: Position3D = Position3D(0,0,0),
            velocity_x: float = 0,
            velocity_y: float = 0,
            velocity_z: float = 0,
            mass: float = 1,
            max_speed: float = 100,
            max_force: float = 200,
            max_altitude: int = 10000,
            max_turn_rate: float = math.pi,
            scale: float = 10.0,
            action: str = 'none',
            ):
        super().__init__(
            vehicle_type,
            vehicle_id,
            destination_queue,
            time_step,
            action,
            )
        self._position: Position3D = position
        self._velocity: Position3D = Position3D(velocity_x, velocity_y, velocity_z)
        self._acceleration: Position3D = Position3D(0,0,0)
        self.mass : np.float64 = np.float64(mass)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.max_turn_rate: np.float64 = np.float64(max_turn_rate)
        self.heading: np.float64 = np.float64(0)
        self.scale: float = scale
        self.max_altitude: int = max_altitude
        self.vertices = self._build_arrow()
        self.target: Position3D = Position3D(0,0,0)
        # Inherited from Vehicle:
        # self.next_destination: Destination = None
        # self.action : str = 'none'

    @property
    def pos_x(self) -> float:
        return self.position.x

    @pos_x.setter
    def pos_x(self, value: float) -> None:
        self.position.x = value

    @property
    def pos_y(self) -> float:
        return self.position.y

    @pos_y.setter
    def pos_y(self, value: float) -> None:
        self.position.y = value

    @property
    def pos_z(self) -> float:
        return self.position.z
    
    @pos_z.setter
    def pos_z(self, value: float) -> None:
        self.position.z = value

    @property
    def position(self) -> Position3D:
        return Position3D(self._position.x, self._position.y, self._position.z)
    
    @position.setter
    def position(self, position: Position3D) -> None:
        self._position = position

    @property
    def velocity_x(self) -> float:
        return self._velocity.x

    @velocity_x.setter
    def velocity_x(self, value: float) -> None:
        self._velocity.x = value

    @property
    def velocity_y(self) -> float:
        return self._velocity.y

    @velocity_y.setter
    def velocity_y(self, value: float) -> None:
        self._velocity.y = value

    @property
    def velocity_z(self) -> float:
        return self._velocity.z
    
    @velocity_z.setter
    def velocity_z(self, value: float) -> None:
        self._velocity.z = value

    @property
    def velocity(self) -> Position3D:
        return Position3D(self._velocity.x, self._velocity.y, self._velocity.z)

    @velocity.setter
    def velocity(self, velocity: Position3D) -> None:
        self._velocity = Position3D(velocity.x, velocity.y, velocity.z)    

    @property
    def acceleration_x(self) -> float:
        return self._acceleration.x

    @property
    def acceleration_y(self) -> float:
        return self._acceleration.y
    
    @property
    def acceleration_z(self) -> float:
        return self._acceleration.z

    @property
    def acceleration(self) -> Position3D:
        return Position3D(self._acceleration.x, self._acceleration.y, self._acceleration.z)

    @acceleration.setter
    def acceleration(self, acceleration: Position3D) -> None:
        self._acceleration = Position3D(acceleration.x, acceleration.y, acceleration.z)
        
    def _build_arrow(self) -> NDArray[np.float64]:
        return np.array([
            [1, 0],
            [-1, 0.5],
            [-0.5, 0],
            [-1, -0.5]
        ], dtype=np.float64) * self.scale
    
    def _assign_next_destination(self) -> bool:
        """Assign the next destination and set target to the destination's position."""
        success = super()._assign_next_destination()
        if success and self.next_destination:
            self.target = self.next_destination.position
        return success

    def seek(self) -> Position3D:
        """Calculate steering force towards target in 3D space."""
        desired_direction = normalize(self.target - self.position)
        desired_velocity = scale_position(desired_direction, min(self.max_speed, self.target_speed()))
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def flee(self) -> Position3D:
        """Calculate steering force away from target in 3D space."""
        desired_direction = normalize(self.position - self.target)
        desired_velocity = scale_position(desired_direction, -min(self.max_speed, self.target_speed()))
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def arrive(self) -> Position3D:
        """Calculate steering force to arrive smoothly at target in 3D space."""
        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)
        if distance < 1:
            return Position3D(0.0, 0.0, 0.0)
        desired_direction = normalize(to_target)
        speed = min(distance / 0.3, min(self.max_speed, self.target_speed()))
        desired_velocity = scale_position(desired_direction, speed)
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def update(self, dt: float, window_w: int, window_h: int) -> None:
        """Update vehicle position and state."""
        if self.next_destination is None:
            if not self._has_next_destination():
                self.action = 'done'
            self._assign_next_destination()
        elif self.next_destination.has_reached(self.position):
            self._assign_next_destination()
        distance_to_target = self.position.distance_to(self.target)
        if self.action == 'seek':
            self.acceleration = self.seek()
        elif self.action == 'flee':
            if distance_to_target < 300:
                self.acceleration = self.flee()
            else:
                self.acceleration = Position3D(0.0, 0.0, 0.0)
        elif self.action == 'arrive':
            self.acceleration = self.arrive()
        else:
            self.acceleration = Position3D(0.0, 0.0, 0.0)
            self.action = 'done'
        self._velocity = truncate(self._velocity + scale_position(self._acceleration, dt), self.max_speed)
        self.position += scale_position(self._velocity, dt)
        if self._velocity.distance_to(Position3D(0, 0, 0)) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)
        self.pos_x = self.position.x % window_w
        self.pos_y = self.position.y % window_h
        self.pos_z = max(0, min(self.position.z, self.max_altitude))
