import queue, math
import numpy as np
from numpy.typing import NDArray
from .Vehicle import Vehicle
from .Position import Position3D
from .Vectors import Vector3D

# Helper functions adapted to use Vector3D (positions are Position3D)
def _as_vector3d(pos: Position3D) -> Vector3D:
    return Vector3D(float(pos.x), float(pos.y), float(pos.z))


def normalize(v: Vector3D) -> Vector3D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        scaled = vec / norm
        return Vector3D(float(scaled[0]), float(scaled[1]), float(scaled[2]))
    return Vector3D(0.0, 0.0, 0.0)


def truncate(v: Vector3D, limit: float) -> Vector3D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > limit:
        scaled = vec * (limit / norm)
        return Vector3D(float(scaled[0]), float(scaled[1]), float(scaled[2]))
    return v


def scale_vector(vec: Vector3D, scalar: float) -> Vector3D:
    return Vector3D(vec.x * scalar, vec.y * scalar, vec.z * scalar)

class Vehicle3D(Vehicle):
    def __init__(
            self,
            vehicle_id: int,
            vehicle_type: str,
            destination_queue: queue.Queue,
            time_step: float,

            position: Position3D = Position3D(0,0,0),
            max_speed: float = 100,
            max_force: float = 200,
            max_altitude: int = 10000,
            scale: float = 10.0,
            action: str = 'seek',
            ):
        super().__init__(
            vehicle_id,
            vehicle_type,
            destination_queue,
            time_step,
            action
            )
        self._position: Position3D = position
        self._velocity: Vector3D = Vector3D(0.0, 0.0, 0.0)
        self._acceleration: Vector3D = Vector3D(0.0, 0.0, 0.0)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.heading: np.float64 = np.float64(0)
        self.scale: float = scale
        self.max_altitude: int = max_altitude
        self.vertices = self._build_arrow()
        self.target: Position3D = Position3D(0,0,0)
        # Inherited from Vehicle:
        # self.next_destination: Destination = None
        # self.done : bool = False

    @property
    def pos_x(self) -> float:
        return self.position.x

    @pos_x.setter
    def pos_x(self, value: float) -> None:
        self._position.x = value

    @property
    def pos_y(self) -> float:
        return self.position.y

    @pos_y.setter
    def pos_y(self, value: float) -> None:
        self._position.y = value

    @property
    def pos_z(self) -> float:
        return self.position.z
    
    @pos_z.setter
    def pos_z(self, value: float) -> None:
        self._position.z = value

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
    def velocity(self) -> Vector3D:
        return Vector3D(self._velocity.x, self._velocity.y, self._velocity.z)

    @velocity.setter
    def velocity(self, velocity: Vector3D) -> None:
        self._velocity = Vector3D(velocity.x, velocity.y, velocity.z)

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
    def acceleration(self) -> Vector3D:
        return Vector3D(self._acceleration.x, self._acceleration.y, self._acceleration.z)

    @acceleration.setter
    def acceleration(self, acceleration: Vector3D) -> None:
        self._acceleration = Vector3D(acceleration.x, acceleration.y, acceleration.z)
        
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

    def seek(self) -> Vector3D:
        """Calculate steering force towards target in 3D space."""
        to_target = self.target - self.position
        desired_direction = normalize(_as_vector3d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def flee(self) -> Vector3D:
        """Calculate steering force away from target in 3D space."""
        to_target = self.target - self.position
        desired_direction = normalize(_as_vector3d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, -desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def arrive(self) -> Vector3D:
        """Calculate steering force to arrive smoothly at target in 3D space."""
        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)
        if distance < 1:
            return Vector3D(0.0, 0.0, 0.0)
        desired_direction = normalize(_as_vector3d(to_target))
        speed = min(distance / 0.3, min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, float(speed))
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def update(self, dt: float) -> None:
        """Update vehicle position and state."""
        if self.done:
            return
        if self.next_destination is None:
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return

        if self.action == 'seek':
            self.acceleration = self.seek()
        elif self.action == 'flee':
            distance_to_target = self.position.distance_to(self.target)
            if distance_to_target < 300:
                self.acceleration = self.flee()
            else:
                self.acceleration = Vector3D(0.0, 0.0, 0.0)
        elif self.action == 'arrive':
            self.acceleration = self.arrive()
        else:
            self.done = True
            self.acceleration = Vector3D(0.0, 0.0, 0.0)

        self._velocity = truncate(
            self._velocity + scale_vector(self._acceleration, float(dt)),
            float(self.max_speed),
        )
        self.position = self.position + scale_vector(self._velocity, float(dt))

        if np.linalg.norm(self._velocity.vector) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)

        self.pos_z = max(0, min(self.position.z, self.max_altitude))

        if self.next_destination.has_reached(self.position):
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return