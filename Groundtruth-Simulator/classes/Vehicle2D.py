import queue, math
import numpy as np
from numpy.typing import NDArray
from .Vehicle import Vehicle
from .Position import Position2D
from .Vectors import Vector2D
from .Settings import Settings
from datetime import datetime as dt
#import xarray as xr
from .Unit_conversions import local_to_geodetic

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
            target_id: int | None = None,
            follow_distance: float = 0.0,
            stay_time: str | float = 0.0,
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
        self.vertices =    self._build_arrow()
        self.target: Position2D = Position2D(0.0, 0.0)
        self.target_id: int | None = target_id
        self.follow_distance: float = follow_distance
        self.follow_ticks: int = 0
        # Inherited from Vehicle:
        # self.next_destination: Destination = DoneDestination()
        
        self.stay_time: dt | int = stay_time if isinstance(stay_time, float | int) else dt.fromisoformat(stay_time)

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

    __str__ = lambda self: f"Vehicle2D(id={self.vehicle_id}, type={self.vehicle_type}, position=({self.position.x}, {self.position.y}), velocity=({self.velocity.x}, {self.velocity.y}), action={self.action})"

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
    
    def follow(self, target_vehicle: 'Vehicle2D', follow_distance: float) -> Vector2D:
        """
        Follow a target vehicle while maintaining an offset position.
        
        :param target_vehicle: The vehicle to follow.
        :param follow_distance: The distance to maintain behind the target vehicle.
        :return: Steering force as a Position2D object.
        """
        follow_distance = float(max(0.0, follow_distance))

        dt = max(float(self.time_step), 1e-9)
        stop_speed = 0.5
        settle_time_s = 2.0
        stop_radius = 1.0

        leader_velocity = target_vehicle.velocity
        leader_speed = float(np.linalg.norm(leader_velocity.vector))
        if leader_speed > 1e-6:
            leader_direction = normalize(leader_velocity)
        else:
            leader_direction = Vector2D(math.cos(target_vehicle.heading), math.sin(target_vehicle.heading))

        self.target = target_vehicle.position + scale_vector(leader_direction, -follow_distance)

        to_target = self.target - self.position
        distance = float(np.linalg.norm(to_target.vector))

        # If the leader is finished, treat this like a terminal arrive-and-stop.
        if target_vehicle.done:
            follower_speed = float(np.linalg.norm(self.velocity.vector))
            if distance < follow_distance and follower_speed < stop_speed:
                self.follow_ticks += 1
            else:
                self.follow_ticks = 0

            if self.follow_ticks * dt >= settle_time_s:
                self.done = True
                return Vector2D(0.0, 0.0)

            desired_speed = 0.0 if distance < stop_radius else min(float(self.max_speed), distance / dt)
        else:
            # Leader still moving: ignore leader speed. Set desired speed purely from how far we are
            # from the moving follow point. Using distance/time_step makes the follower naturally
            # converge to the leader's speed once it is tracking well.
            self.follow_ticks = 0
            desired_speed = min(float(self.max_speed), distance / dt)

        if distance < 1e-9 or desired_speed <= 0.0:
            desired_velocity = Vector2D(0.0, 0.0)
        else:
            desired_direction = normalize(_as_vector2d(to_target))
            desired_velocity = scale_vector(desired_direction, float(desired_speed))

        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def pursue(self, target_vehicle: 'Vehicle2D', dt: float) -> Vector2D:
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

        to_target = self.target - self.position
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = min(float(self.max_speed), distance / dt)
        desired_velocity = scale_vector(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))

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
    
    def stay(self, settings: Settings) -> None:
        if self.position.distance_to(self.target) > self.next_destination.error:
            self.update_kinematics(settings.time_step, self.arrive())
            return
        else:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings.time_step, Vector2D(0.0, 0.0))
            if isinstance(self.stay_time, int | float):
                if self.stay_time < 0:
                        self._assign_next_destination()
                        return
                else:
                    self.stay_time -= settings.time_step
                    return
            else:
                if settings.current_simulation_time <= self.stay_time:
                    return
                else:
                    self._assign_next_destination()


    def collision_avoidance(self):
        pass

    def update_kinematics(self, settings: Settings, acceleration: Vector2D) -> None:
        """Update vehicle kinematics based on acceleration."""
        self.acceleration = acceleration
        self.velocity = truncate(self.velocity + scale_vector(self.acceleration, float(settings.time_step)), float(self.max_speed))
        purposed_position = self.position + scale_vector(self.velocity, float(settings.time_step))
        if self.position.distance_to(purposed_position) < self.position.distance_to(self.target):
            x, y, z = local_to_geodetic(self.position.x, self.position.y, settings=settings)
            self.position = purposed_position + scale_vector(settings.ocean_current.get_current(y, x), 100000 * float(settings.time_step)) 
        else:
            self.position = self.target
            self.velocity = truncate(self.velocity + scale_vector(self.acceleration, float(settings.time_step)), float(self.max_speed))
        
        if np.linalg.norm(self.velocity.vector) > 1e-6:
            direction = normalize(self.velocity)
            self.heading = math.atan2(direction.y, direction.x)


    def has_reached_destination(self) -> bool:
        if self.next_destination.has_reached(self.position):
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return True
        return False


    def update(self, settings: Settings, vehicles, ) -> None:
        if self.done:
            return
        """Update vehicle position and state."""
        if self.action == 'follow':
            self.follow_update(settings, vehicles)
        elif self.action == 'pursue':
            self.pursue_update(settings, vehicles)
        else:
            self.standard_update(settings)


    def standard_update(self, settings: Settings) -> None:
        """Update vehicle position and state."""
        if self.next_destination is None:
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return

        if self.action == 'seek':
            self.update_kinematics(settings, self.seek())
        elif self.action == 'flee':
            distance_to_target = self.position.distance_to(self.target)
            if distance_to_target < 1000:
                self.update_kinematics(settings, self.flee())
            else:
                if self._has_next_destination():
                    self._assign_next_destination()
                else:
                    self.done = True
        elif self.action == 'arrive':
            self.update_kinematics(settings, self.arrive())
        elif self.action == 'stay':
            self.stay(settings)
            return
        else:
            self.done = True
            self.update_kinematics(settings, Vector2D(0.0, 0.0))

        self.has_reached_destination()

            
    def follow_update(self, settings: Settings, vehicles) -> None:
        """Update vehicle position and state for follow action."""
        target_vehicle = next((v for v in vehicles if v.vehicle_id == self.target_id), None)
        if target_vehicle is None:
            print(f"Vehicle {self.vehicle_id} cannot find target vehicle {self.target_id} to follow.")
            self.done = True
            return
        
        self.update_kinematics(settings, self.follow(target_vehicle, self.follow_distance))

    def stay_update(self, settings: Settings) -> None:
        if self.done:
            return
        if self.next_destination is None:
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return
        if not self.next_destination.has_reached(self.position):
            self.update_kinematics(settings, self.arrive())
            return
        
        else:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings, Vector2D(0.0, 0.0))
            if isinstance(self.stay_time, int | float):
                if self.stay_time < 0:
                    if self._has_next_destination():
                        self._assign_next_destination()
                    else:
                        self.done = True
                        return
                else:
                    self.stay_time -= settings.time_step
            else:
                if settings.current_simulation_time <= self.stay_time:
                    return
                else:
                    if self._has_next_destination():
                        self._assign_next_destination()
                    else:
                        self.done = True
                        return
                    
    def pursue_update(self, settings: Settings, vehicles) -> None:
        """Update vehicle position and state for pursue action."""
        target_vehicle = next((v for v in vehicles if v.vehicle_id == self.target_id), None)
        if self.position.distance_to(target_vehicle.position) < 1e-6:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings, Vector2D(0.0, 0.0))
            self.done = True
            return
        if target_vehicle is None:
            print(f"Vehicle {self.vehicle_id} cannot find target vehicle {self.target_id} to pursue.")
            self.done = True
            return
        if self.position.distance_to(target_vehicle.position) < 1e-6:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings, Vector2D(0.0, 0.0))
            self.done = True
            return
        
        self.update_kinematics(settings, self.pursue(target_vehicle, settings.time_step))

