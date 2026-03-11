import queue, math
import numpy as np
from numpy.typing import NDArray
# Assuming Position, PositionUTM, Position3D, PositionLatLon are in 'classes' module
from .Position import Position, PositionUTM, Position3D
# Assuming Vehicle is imported from classes.Vehicle
from .Vehicle import Vehicle
# Assuming utm conversion functions are imported (from helpers.coordinate_converters)
from helpers.utm import latlon_to_utm, utm_to_latlon # Corrected import
# Need Vehicle2D to inherit from
from .Vehicle2D import Vehicle2D as BaseVehicle2D
from .Vectors import Vector3D
from .Settings import Settings
from datetime import datetime as dt


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

class Vehicle3D(BaseVehicle2D): # Inherit from the new Vehicle2D
    def __init__(
            self,
            vehicle_id: int,
            vehicle_type: str,
            destination_queue: queue.Queue,
            time_step: float = 1, # Default time_step

            # Global Lat/Lon position is now the primary input for initialization
            initial_global_latitude: float = 42.00107,
            initial_global_longitude: float = -111.33747,
            initial_global_altitude: float = 0.0, # New parameter for 3D

            max_speed: float = 100.0,
            max_force: float = 200.0,
            max_altitude: float = 10000.0, # Float for consistency
            scale: float = 10.0,
            action: str = 'seek',
            target_id: int | None = None,
            follow_distance: float = 0.0,
            stay_time: str | float = 0.0,
            ):
        # Call the parent's (Vehicle2D's) constructor
        super().__init__(
            vehicle_id=vehicle_id,
            vehicle_type=vehicle_type,
            destination_queue=destination_queue,
            time_step=time_step,
            initial_global_latitude=initial_global_latitude,
            initial_global_longitude=initial_global_longitude,
            max_speed=max_speed,
            max_force=max_force,
            scale=scale,
            action=action,
            )
        self._velocity: Vector3D = Vector3D(0.0, 0.0, 0.0)
        self._acceleration: Vector3D = Vector3D(0.0, 0.0, 0.0)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.heading: np.float64 = np.float64(0)
        self.scale: float = scale
        self.max_altitude: int = max_altitude
        self.vertices = self._build_arrow()
        self.target: Position3D = Position3D(0,0,0)
        self.target_id: int | None = target_id
        self.follow_distance: float = follow_distance
        self.follow_ticks: int = 0
        self.stay_time: dt | float = stay_time if isinstance(stay_time, float | int) else dt.fromisoformat(stay_time)
        # Inherited from Vehicle:
        # self.next_destination: Destination = None
        # self.done : bool = False
        self.initial_global_latitude=initial_global_latitude,
        self.initial_global_longitude=initial_global_longitude,
        self.max_speed=max_speed,
        self.max_force=max_force,
        self.scale=scale

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
        # Override the _position_utm (from PositionUTM) to Position3D
        # and ensure _velocity, _acceleration are also 3D.
        # super().__init__ already set _position_utm as a PositionUTM based on initial Lat/Lon.
        # Now, we "upgrade" _position_utm to Position3D, adding the initial altitude.
        self._position_utm: Position3D = Position3D(
            self._position_utm.x,
            self._position_utm.y,
            self.initial_global_altitude
        )
        # Velocity and acceleration also need to be 3D
        self._velocity: Position3D = Position3D(0.0, 0.0, 0.0)
        self._acceleration: Position3D = Position3D(0.0, 0.0, 0.0)
        
        self.max_altitude: float = float(self.max_altitude) # Ensure float type
        
        # Target for local steering, should be in 3D UTM
        self.target: Position3D = Position3D(
            self._position_utm.x,
            self._position_utm.y,
            self._position_utm.z
        )

    # --- Properties ---
    @property
    def pos_z(self) -> float:
        return self.position.z
    
    @pos_z.setter
    def pos_z(self, value: float) -> None:
        # Create a new Position3D object to trigger the main @position.setter
        new_pos = Position3D(self.position.x, self.position.y, value)
        self.position = new_pos # This will call the main @position.setter

    @property
    def position(self) -> Position3D:
        """
        Returns the current UTM position (easting, northing, altitude).
        """
        return self._position_utm
    
    @position.setter
    def position(self, new_utm_position: Position3D) -> None:
        """
        Sets the UTM position. This setter will convert the new UTM coordinates
        (x,y) back to Lat/Lon and then use the parent's global_position setter to handle
        zone re-evaluation and coordinate updates for x,y. The altitude (z) is
        updated directly and clamped.
        """
        if not isinstance(new_utm_position, Position3D):
            raise TypeError("position for Vehicle3D must be a Position3D object (easting, northing, altitude).")

        if self._utm_zone_number == 0 or not self._utm_zone_letter:
             raise ValueError("UTM zone info not set for 3D vehicle before setting UTM position directly.")

        lat, lon = utm_to_latlon(
            new_utm_position.x,
            new_utm_position.y,
            self._utm_zone_number,
            self._utm_zone_letter
        )
        
        # --- FIX HERE: Call the parent's property setter ---
        # This will update self._global_position_latlon and self._position_utm (x,y)
        # BUT it will set self._position_utm to a PositionUTM object.
        BaseVehicle2D.global_position.fset(self, PositionUTM(lat, lon))

        # --- SECOND FIX HERE: Re-cast _position_utm back to Position3D ---
        # After the parent setter runs, self._position_utm is PositionUTM.
        # We need it to be Position3D for a 3D vehicle.
        # We reconstruct it using its current X, Y and the new Z.
        if not isinstance(self._position_utm, Position3D):
            self._position_utm = Position3D(self._position_utm.x, self._position_utm.y, 0.0) # Default Z for recasting

        # Now, update the Z component (altitude) for the (now correctly typed) 3D UTM position
        clamped_z = np.clip(new_utm_position.z, 0.0, self.max_altitude)
        self._position_utm.z = float(clamped_z)


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

    __str__ = lambda self: f"Vehicle3D(id={self.vehicle_id}, type={self.vehicle_type}, position=({self.position.x}, {self.position.y}, {self.position.z}), velocity=({self.velocity.x}, {self.velocity.y}, {self.velocity.z}), action={self.action})"
        
    # --- Methods ---

    def _build_arrow(self) -> NDArray[np.float64]:
        # For now, keeping 2D projection on X,Y plane, but storing as 3D vectors
        return np.array([
            [1, 0, 0], # x, y, z
            [-1, 0.5, 0],
            [-0.5, 0, 0],
            [-1, -0.5, 0]
        ], dtype=np.float64) * self.scale
    
    def _assign_next_destination(self) -> bool:
        """Assign the next destination and set target to the destination's position."""
        success = super()._assign_next_destination() 
        if success and self.next_destination:
            if not isinstance(self.next_destination.position, Position3D):
                raise TypeError("3D vehicle's destination position must be Position3D.")
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
    
    def follow(self, target_vehicle: 'Vehicle3D', follow_distance: float) -> Vector3D:
        follow_distance = float(max(0.0, follow_distance))

        dt = max(float(self.time_step), 1e-9)
        stop_speed = 0.5
        settle_time_s = 5.0
        stop_radius = 1.0

        leader_velocity = target_vehicle.velocity
        leader_speed = np.linalg.norm(leader_velocity.vector)
        if leader_speed > 1e-6:
            leader_direction = normalize(leader_velocity)
        else:
            leader_direction = Vector3D(math.cos(target_vehicle.heading), math.sin(target_vehicle.heading), 0.0)

        self.target = target_vehicle.position + scale_vector(leader_direction, -follow_distance)

        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)

        if target_vehicle.done:
            follower_speed = float(np.linalg.norm(self.velocity.vector))
            if distance < follow_distance and follower_speed < stop_speed:
                self.follow_ticks += 1
            else:
                self.follow_ticks = 0

            if self.follow_ticks * dt >= settle_time_s:
                self.done = True
                return Vector3D(0.0, 0.0, 0.0)
            desired_speed = 0.0 if distance < stop_radius else min(float(self.max_speed), distance / dt)

        else:
            self.follow_ticks = 0
            desired_speed = min(float(self.max_speed), distance / dt)  
        
        if distance < 1e-9 or desired_speed <= 0.0:
            desired_velocity = Vector3D(0.0, 0.0, 0.0)
        else:
            desired_direction = normalize(_as_vector3d(to_target))
            desired_velocity = scale_vector(desired_direction, float(desired_speed))
        
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def stay(self) -> None:
        pass

    def update_kinematics(self, dt: float) -> None:
        self._velocity = truncate(
            self._velocity + scale_vector(self._acceleration, float(dt)),
            float(self.max_speed),
        )
        self.position = self.position + scale_vector(self._velocity, float(dt))

        if np.linalg.norm(self._velocity.vector) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)
        self.pos_z = max(0, min(self.position.z, self.max_altitude))

        
    def update(self, settings: Settings, vehicles) -> None:
        if self.action == 'follow':
            self.follow_update(settings.time_step, vehicles)
        elif self.action == 'stay':
            self.stay_update(settings)
        else:
            self.standard_update(settings.time_step, vehicles)

    def standard_update(self, dt: float, vehicles) -> None:
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

        self.update_kinematics(dt)
        self._velocity = truncate(
            self._velocity + scale_vector(self._acceleration, float(dt)),
            float(self.max_speed),
        )
        self.position = self.position + scale_vector(self._velocity, float(dt))

        if np.linalg.norm(self._velocity.vector) > 1e-6:
            direction = normalize(self._velocity)
            self.heading = math.atan2(direction.y, direction.x)

        if self._velocity.magnitude() > 1e-6: 
            horizontal_speed_sq = self._velocity.x**2 + self._velocity.y**2
            if horizontal_speed_sq > 1e-12:
                self.heading = math.atan2(self._velocity.y, self._velocity.x)

        if self.next_destination.has_reached(self.position):
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return
            
    def follow_update(self, dt: float, vehicles) -> None:
        """Update vehicle position and state when following another vehicle."""
        if self.done:
            return
        target_vehicle = next((v for v in vehicles if v.vehicle_id == self.follow_id), None)
        if target_vehicle is None:
            print(f"Vehicle {self.vehicle_id} cannot find target vehicle {self.follow_id} to follow.")
            self.done = True
            return
        
        self.acceleration = self.follow(target_vehicle, self.follow_distance)

        self.update_kinematics(dt)

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
            self.acceleration = self.seek()
            self.update_kinematics(settings.time_step)
            return
        else:
            self.acceleration = Vector3D(0.0, 0.0, 0.0)
            self.velocity = Vector3D(0.0, 0.0, 0.0)
            self.update_kinematics(settings.time_step)
            if isinstance(self.stay_time, int | float):
                self.stay_time -= settings.time_step
                if self.stay_time < 0:
                    if self._has_next_destination():
                        self._assign_next_destination()
                    else:
                        self.done = True
                        return
            else:
                if settings.current_simulation_time <= self.stay_time:
                    return
                else:
                    if self._has_next_destination():
                        self._assign_next_destination()
                    else:
                        self.done = True
                        return