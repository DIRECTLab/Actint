import queue, math
import numpy as np
from datetime import datetime as dt
from numpy.typing import NDArray
from .Vehicle import Vehicle
from .Vectors import Vector2D
from .Settings import Settings
from .Position import PositionUTM, PositionLatLon
from helpers import utm

# Helper functions adapted to use Vector2D (positions are PositionUTM)
def _as_vector2d(pos: PositionUTM) -> Vector2D:
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
            
            initial_global_latitude: float = 42.00107,
            initial_global_longitude: float = -111.33747,

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
        
        # Internal storage for UTM and Lat/Lon. These are private attributes.
        # Initialize with dummy values, then set via global_position to ensure consistency
        self._position_utm: PositionUTM = PositionUTM(0, 0, 0, '') # UTM Easting, Northing
        self._position_latlon: PositionLatLon = PositionLatLon(0.0, 0.0) # Latitude, Longitude
                
        # Set the initial global position through its setter to correctly initialize both _position_latlon, _position_utm, and UTM zone info.
        self.position_latlon = PositionLatLon(initial_global_latitude, initial_global_longitude)

        # Velocity and acceleration should be in UTM (Vector2D/PositionUTM for components)
        self._velocity: Vector2D = Vector2D(0.0, 0.0)
        self._acceleration: Vector2D = Vector2D(0.0, 0.0)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.heading: np.float64 = np.float64(0.0)
        self.scale: float = scale
        self.target_id: int | None = target_id
        self.follow_distance: float = follow_distance
        self.follow_ticks: int = 0
        # Inherited from Vehicle:
        # self.next_destination: Destination = DoneDestination()
        
        self.stay_time: dt | int = stay_time if isinstance(stay_time, float | int) else dt.fromisoformat(stay_time)
        self.vertices = self._build_arrow() # Assumes this uses self.position_utm (UTM)
        self.target: PositionUTM = PositionUTM(0.0, 0.0, 0, '') # Target for local steering, should be in UTM

    @property
    def utm_number(self) -> int:
        return self.position_utm.number
    
    @property
    def utm_letter(self) -> str:
        return self.position_utm.letter
    @property
    def position_utm(self) -> PositionUTM:
        """
        Returns the current UTM position (easting, northing).
        """
        return self._position_utm

    @position_utm.setter
    def position_utm(self, new_utm_position: PositionUTM):
        """
        Sets the UTM position. This setter converts the new UTM coordinates
        back to Lat/Lon and updates both internal representations
        (_position_utm and _position_latlon) directly, avoiding a loop.
        """
        if not isinstance(new_utm_position, PositionUTM):
            raise TypeError("position_utm must be a PositionUTM object (easting, northing).")

        # Determine which zone to use for the reverse projection.
        # Prefer zone info carried by the new PositionUTM (if present), otherwise
        # fall back to the vehicle's current zone.
        zone_number = new_utm_position.number or self.utm_number
        zone_letter = new_utm_position.letter or self.utm_letter

        if zone_number == 0 or not zone_letter:
            raise ValueError(
                "UTM zone number and letter must be set (via position_latlon) "
                "before setting UTM position directly."
            )

        # Convert the new UTM position to Lat/Lon.
        lat, lon = utm.utm_to_latlon(
            new_utm_position.x,
            new_utm_position.y,
            zone_number,
            zone_letter,
        )

        # Set the raw UTM first, then route through position_latlon to allow
        # zone-crossing detection and consistent rebasing.
        self._position_utm = PositionUTM(
            float(new_utm_position.x),
            float(new_utm_position.y),
            int(zone_number),
            str(zone_letter),
        )
        self.position_latlon = PositionLatLon(float(lat), float(lon))

    # Back-compat alias used by follow/pursue/evade code and by Vehicle3D.
    @property
    def position(self) -> PositionUTM:
        return self.position_utm

    @position.setter
    def position(self, new_position: PositionUTM) -> None:
        self.position_utm = new_position

    @property
    def easting(self) -> float:
        return self.position_utm.x
    
    @property
    def northing(self) -> float:
        return self.position_utm.y

    @property
    def position_latlon(self) -> PositionLatLon:
        """
        Returns the current global Lat/Lon position (latitude, longitude).
        """
        return self._position_latlon

    @position_latlon.setter
    def position_latlon(self, new_position_latlon: PositionLatLon):
        """
        Sets the Lat/Lon position and automatically updates the UTM position
        and its corresponding UTM zone number and letter.
        This setter is responsible for detecting UTM zone crossings and rebasing.
        It directly updates the internal _position_utm to prevent a loop.
        """
        if not isinstance(new_position_latlon, PositionLatLon):
            raise TypeError("position_latlon must be a PositionLatLon object (latitude, longitude).")

        # Store the new position_latlon
        self._position_latlon = new_position_latlon

        # Convert the new Lat/Lon position to UTM
        # Note: Using new_position_latlon.latitude/longitude for clarity with the conversions
        pos_easting, pos_northing, new_zone_num, new_zone_letter = utm.latlon_to_utm(
            new_position_latlon.latitude,
            new_position_latlon.longitude,
        )


        # Rebase the target to the new UTM zone to maintain consistency. This ensures
        # that the target is always in the same UTM zone as the current position.
        if self.next_destination is not None and self.next_destination.position is not None:
            dest_lat = self.next_destination.position.latitude
            dest_lon = self.next_destination.position.longitude

            dest_easting, dest_northing = utm.utm_zone_projection(
                zone_number=new_zone_num,
                zone_letter=new_zone_letter,
                latitude=dest_lat,
                longitude=dest_lon,
            )
            self.target = PositionUTM(
                float(dest_easting),
                float(dest_northing),
                int(new_zone_num),
                str(new_zone_letter),
            )

        # Update the UTM position regardless of zone change
        # This *must* directly update the internal attribute
        # to avoid calling the 'position' setter and creating a loop.
        self._position_utm = PositionUTM(
            float(pos_easting),
            float(pos_northing),
            int(new_zone_num),
            str(new_zone_letter),
        )

    @property
    def utm_zone(self) -> tuple[int, str]:
        """
        Returns the current UTM zone number and letter.
        """
        return self.utm_number, self.utm_letter

    @property
    def latitude(self) -> float:
        return self.position_latlon.latitude
    
    @property
    def longitude(self) -> float:
        return self.position_latlon.longitude

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

    __str__ = lambda self: f"Vehicle2D(id={self.vehicle_id}, type={self.vehicle_type}, UTMposition=({self.easting}, {self.northing}), LatLonposition=({self.position_latlon.latitude}, {self.position_latlon.longitude}), velocity=({self.velocity.x}, {self.velocity.y}), action={self.action})"

    def _build_arrow(self) -> NDArray[np.float64]:
        # Remains the same, operates on UTM (x, y) coordinates
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
            lat = self.next_destination.position.latitude
            lon = self.next_destination.position.longitude
            # Always keep `self.target` in UTM coordinates (PositionUTM). Note that
            # `utm_zone_projection` returns (easting, northing) as a tuple.
            easting, northing = utm.utm_zone_projection(
                zone_number=self.utm_number,
                zone_letter=self.utm_letter,
                latitude=lat,
                longitude=lon,
            )
            self.target = PositionUTM(float(easting), float(northing), self.utm_number, self.utm_letter)
        return success
      
    def seek(self) -> Vector2D:
        """Calculate steering force towards target in 2D space (UTM)."""
        to_target = self.target - self.position_utm
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def flee(self) -> Vector2D:
        """Calculate steering force away from target in 2D space (UTM)."""
        to_target = self.target - self.position_utm
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = float(min(self.max_speed, self.target_speed()))
        desired_velocity = scale_vector(desired_direction, -desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))
    
    def arrive(self) -> Vector2D:
        """Calculate steering force to arrive smoothly at target in 2D space (UTM)."""
        to_target = self.target - self.position_utm
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
        :return: Steering force as a PositionUTM object.
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

        to_target = self.target - self.position_utm
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
        
        :param target_vehicle: The vehicle to pursue.
        :return: Steering force as a PositionUTM object.
        """
        to_target = target_vehicle.position - self.position_utm
        distance = np.linalg.norm(to_target.vector)
        sim_time_steps = distance / (self.max_speed + 1e-9)  # Avoid division by zero
        self.target = target_vehicle.position + scale_vector(target_vehicle.velocity, float(sim_time_steps))

        to_target = self.target - self.position_utm
        desired_direction = normalize(_as_vector2d(to_target))
        desired_speed = min(float(self.max_speed), distance / dt)
        desired_velocity = scale_vector(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, float(self.max_force))

    def evade(self, target_vehicle: 'Vehicle2D') -> Vector2D:
        """
        Predict the future position of the target vehicle and flee from that position.
        
        :param target_vehicle: The vehicle to evade.
        :return: Vector representing the steering force to evade the target vehicle.
        """
        to_target = target_vehicle.position - self.position_utm
        distance = np.linalg.norm(to_target.vector)
        sim_time_steps = distance / (self.max_speed + 1e-9)  # Avoid division by zero
        self.target = target_vehicle.position + scale_vector(target_vehicle.velocity, float(sim_time_steps))

        return self.flee()
    
    def stay(self, settings: Settings) -> None:
        if self.position_utm.distance_to(self.target) > self.next_destination.error:
            self.update_kinematics(settings, self.arrive())
            return
        else:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings, Vector2D(0.0, 0.0))
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
        dt_s = float(settings.time_step)
        self.velocity = truncate(
            self.velocity + scale_vector(self.acceleration, dt_s),
            float(self.max_speed),
        )
        purposed_position = self.position_utm + scale_vector(self.velocity, dt_s)
        if self.position_utm.distance_to(purposed_position) < self.position_utm.distance_to(self.target):
            # Currents are expected to be a velocity-like vector (e.g., m/s).
            # Convert to displacement in meters by multiplying by dt.
            current_disp = scale_vector(
                settings.ocean_current.get_current(lat=self.latitude, lon=self.longitude),
                dt_s,
            )
            self.position_utm = purposed_position + current_disp
        else:
            self.position_utm = self.target
        
        if np.linalg.norm(self.velocity.vector) > 1e-6:
            direction = normalize(self.velocity)
            self.heading = math.atan2(direction.y, direction.x)


    def has_reached_destination(self) -> bool:
        if not utm.same_utm_zone(self.next_destination.position, self.position_latlon):
            return False
        elif self.next_destination.has_reached(self.position_latlon):
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
            distance_to_target = self.position_utm.distance_to(self.target)
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

        # Kinematics integration (velocity/position/heading) happens inside
        # update_kinematics(). Do not integrate a second time here.

            
    def follow_update(self, settings: Settings, vehicles) -> None:
        """Update vehicle position and state for follow action."""
        target_vehicle = next((v for v in vehicles if v.vehicle_id == self.target_id), None)
        if target_vehicle is None:
            print(f"Vehicle {self.vehicle_id} cannot find target vehicle {self.target_id} to follow.")
            self.done = True
            return
        
        self.update_kinematics(settings, self.follow(target_vehicle, self.follow_distance))

    def stay_update(self, settings: Settings) -> None:
        if self.next_destination is None:
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return
        if not self.next_destination.has_reached(self.position_utm):
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
        if target_vehicle is None:
            print(f"Vehicle {self.vehicle_id} cannot find target vehicle {self.target_id} to pursue.")
            self.done = True
            return
        if self.position_utm.distance_to(target_vehicle.position) < 1e-6:
            self.velocity = Vector2D(0.0, 0.0)
            self.update_kinematics(settings, Vector2D(0.0, 0.0))
            self.done = True
            return
        
        self.update_kinematics(settings, self.pursue(target_vehicle, settings.time_step))

