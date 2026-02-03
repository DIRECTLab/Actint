import queue, math
import numpy as np
from numpy.typing import NDArray
from .Vehicle import Vehicle
from .Position import Position2D
from .Vectors import Vector2D

# Helper functions adapted to use Vector2D (positions are Position2D)
def _as_vector2d(pos: Position2D) -> Vector2D:
    return Vector2D(float(pos.x), float(pos.y))


def normalize(v: Vector2D) -> Vector2D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        scaled = vec / norm
        return Vector2D(float(scaled[0]), float(scaled[1]))
    return Vector2D(0.0, 0.0)


def truncate(v: Vector2D, limit: float) -> Vector2D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > limit:
        scaled = vec * (limit / norm)
        return Vector2D(float(scaled[0]), float(scaled[1]))
    return v


def scale_vector(vec: Vector2D, scalar: float) -> Vector2D:
    return Vector2D(vec.x * scalar, vec.y * scalar)

class Vehicle2D(Vehicle):
    def __init__(
            self,
            vehicle_id: int,
            vehicle_type: str,
            destination_queue: queue.Queue,
            time_step: float,
            
            position: Position2D = Position2D(0,0),
            max_speed: float = 100.0,
            max_force: float = 200.0,
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
        self._position: Position2D = position
        self._velocity: Vector2D = Vector2D(0.0, 0.0)
        self._acceleration: Vector2D = Vector2D(0.0, 0.0)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.heading: np.float64 = np.float64(0.0)
        self.scale: float = scale
        self.vertices = self._build_arrow()
        self.target: Position2D = Position2D(0.0, 0.0)
        # Inherited from Vehicle:
        # self.next_destination: Destination = DoneDestination()


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
    def position(self) -> Position2D:
        return Position2D(self._position.x, self._position.y)

    @position.setter
    def position(self, position: Position2D) -> None:
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
    def velocity(self) -> Vector2D:
        return Vector2D(self._velocity.x, self._velocity.y)

    @velocity.setter
    def velocity(self, velocity: Vector2D) -> None:
        self._velocity = Vector2D(velocity.x, velocity.y)

    @property
    def acceleration_x(self) -> float:
        return self._acceleration.x

    @property
    def acceleration_y(self) -> float:
        return self._acceleration.y

    @property
    def acceleration(self) -> Vector2D:
        return Vector2D(self._acceleration.x, self._acceleration.y)

    @acceleration.setter
    def acceleration(self, acceleration: Vector2D) -> None:
        self._acceleration = Vector2D(acceleration.x, acceleration.y)

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
      

    def seek(self) -> Vector2D:
        """Calculate steering force towards target in 2D space."""
        to_target = self.target - self.position
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def flee(self) -> Vector2D:
        """Calculate steering force away from target in 2D space."""
        to_target = self.target - self.position
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, -desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def arrive(self) -> Vector2D:
        """Calculate steering force to arrive smoothly at target in 2D space."""
        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)
        if distance < 1:
            return Vector2D(0.0, 0.0)

        if distance < 3:
            desired_speed = 0.01
        elif distance < 200:
            desired_speed = float(min(self.max_speed, self.target_speed())) * (distance / 200)
        else:
            desired_speed = float(min(self.max_speed, self.target_speed()))

        desired_direction = normalize(_as_vector2d(to_target))
        desired_velocity = scale_vector(desired_direction, float(desired_speed))
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def pursue(self, target_vehicle: 'Vehicle2D') -> Vector2D:
        """
        Predict the future position of the target vehicle and seek towards that position.
        
        :param self: Description
        :param target_vehicle: The vehicle to pursue.
        :return: Steering force as a Position2D object.
        """
        to_target = target_vehicle.position - self.position
        distance = np.linalg.norm(to_target.vector)
        sim_time_steps = distance / (self.max_speed + 1e-9)  # Avoid division by zero
        self.target = target_vehicle.position + scale_vector(target_vehicle.velocity, float(sim_time_steps))

        return self.seek()

    def evade(self, target_vehicle: 'Vehicle2D') -> Vector2D:
        """
        Predict the future position of the target vehicle and flee from that position.
        
        :param self: Description
        :param target_vehicle: Description
        :type target_vehicle: 'Vehicle2D'
        :return: Vector representing the steering force to evade the target vehicle.
        :rtype: Vector2D
        """
        to_target = target_vehicle.position - self.position
        distance = np.linalg.norm(to_target.vector)
        sim_time_steps = distance / (self.max_speed + 1e-9)  # Avoid division by zero
        self.target = target_vehicle.position + scale_vector(target_vehicle.velocity, float(sim_time_steps))

        return self.flee()
    
    def follow(self, target_vehicle: 'Vehicle2D', offset: Vector2D) -> Vector2D:
        """
        Follow a target vehicle while maintaining an offset position.
        
        :param target_vehicle: The vehicle to follow.
        :param offset: The offset position to maintain relative to the target.
        :return: Steering force as a Position2D object.
        """
        offset_distance = np.linalg.norm(offset.vector)
        velocity_norm = np.linalg.norm(target_vehicle.velocity.vector)
        if velocity_norm > 1e-9:
            follow_direction = normalize(target_vehicle.velocity)
        else:
            follow_direction = normalize(_as_vector2d(self.position - target_vehicle.position))
        self.target = target_vehicle.position - scale_vector(follow_direction, float(offset_distance))

        return self.seek()


    def stay(self):
        pass

    def colision_avoidance(self):
        pass

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
                self.acceleration = Vector2D(0.0, 0.0)
        elif self.action == 'arrive':
            self.acceleration = self.arrive()
        else:
            self.done = True
            self.acceleration = Vector2D(0.0, 0.0)

        self._velocity = truncate(
            self._velocity + scale_vector(self._acceleration, float(dt)),
            float(self.max_speed),
        )
        self.position = self.position + scale_vector(self._velocity, float(dt))

        if np.linalg.norm(self._velocity.vector) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)

        if self.next_destination.has_reached(self.position):
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return