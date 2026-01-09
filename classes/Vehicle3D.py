import queue
from classes import Vehicle2D, Position
import math
import numpy as np

def normalize(v: Position.Position3D) -> Position.Position3D:
    # Access the underlying numpy array for calculation
    v_vec = v.vector
    norm = np.linalg.norm(v_vec)
    if norm > 1e-9:
        normalized_vec = v_vec / norm
        return Position.Position3D(float(normalized_vec[0]), float(normalized_vec[1]), float(normalized_vec[2]))
    return Position.Position3D(0.0, 0.0, 0.0)

def truncate(v: Position.Position3D, lim: float) -> Position.Position3D:
    # Access the underlying numpy array for calculation
    v_vec = v.vector
    n = np.linalg.norm(v_vec)
    if n > lim:
        truncated_vec = v_vec * (lim / n)
        return Position.Position3D(float(truncated_vec[0]), float(truncated_vec[1]), float(truncated_vec[2]))
    return v

class Vehicle3D(Vehicle2D):
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

        # Inherited from Vehicle2D:
        # self.desired_heading = None # radians

        # Inherited from Vehicle:
        # self.vehicle_type = vehicle_type
        # self.vehicle_id = vehicle_id
        # self.time_step = time_step
        # self.destination_queue = destination_queue
        # self.next_destination: Destination = None

    def seek(self) -> Position.Position3D:
        """
        Calculate steering force towards target in 3D space.
        Combines heading (horizontal direction) and pitch (vertical angle).
        """
        # Get heading and pitch to the target
        heading = self.position.get_heading(self.target)
        pitch = self.position.get_pitch(self.target)
        
        # Convert heading and pitch to 3D direction vector
        # heading: 0 = north (positive y), π/2 = east (positive x), π = south, 3π/2 = west
        # pitch: 0 = horizontal, positive = upward, negative = downward
        
        # Horizontal component (in x-y plane)
        horizontal_mag = math.cos(pitch)  # Reduces as pitch increases
        direction_x = math.sin(heading) * horizontal_mag
        direction_y = math.cos(heading) * horizontal_mag
        direction_z = math.sin(pitch)  # Pure vertical component
        
        desired_direction = normalize(Position.Position3D(direction_x, direction_y, direction_z))
        
        # Scale by max_speed
        desired_velocity = Position.Position3D(
            desired_direction.x * self.max_speed,
            desired_direction.y * self.max_speed,
            desired_direction.z * self.max_speed
        )
        
        # Calculate steering force
        steer = desired_velocity - self.velocity
        return truncate(steer, self.max_force)
    
    def flee(self) -> Position.Position3D:
        """
        Calculate steering force away from target in 3D space.
        Combines heading (horizontal direction) and pitch (vertical angle).
        """
        # Get heading and pitch to the target
        heading = self.position.get_heading(self.target)
        pitch = self.position.get_pitch(self.target)
        
        # Convert heading and pitch to 3D direction vector
        horizontal_mag = math.cos(pitch)  # Reduces as pitch increases
        direction_x = -math.sin(heading) * horizontal_mag
        direction_y = -math.cos(heading) * horizontal_mag
        direction_z = -math.sin(pitch)  # Pure vertical component
        
        desired_direction = normalize(Position.Position3D(direction_x, direction_y, direction_z))
        
        # Scale by max_speed
        desired_velocity = Position.Position3D(
            desired_direction.x * self.max_speed,
            desired_direction.y * self.max_speed,
            desired_direction.z * self.max_speed
        )
        
        # Calculate steering force
        steer = desired_velocity - self.velocity
        return truncate(steer, self.max_force)
    
    def arrive(self) -> Position.Position3D:
        """
        Calculate steering force to arrive smoothly at target in 3D space.
        Combines heading (horizontal direction) and pitch (vertical angle).
        """
        # Get heading and pitch to the target
        heading = self.position.get_heading(self.target)
        pitch = self.position.get_pitch(self.target)
        
        # Convert heading and pitch to 3D direction vector
        horizontal_mag = math.cos(pitch)  # Reduces as pitch increases
        direction_x = math.sin(heading) * horizontal_mag
        direction_y = math.cos(heading) * horizontal_mag
        direction_z = math.sin(pitch)  # Pure vertical component
        
        desired_direction = normalize(Position.Position3D(direction_x, direction_y, direction_z))
        
        # Calculate distance to target
        to_target = self.target - self.position
        distance = np.linalg.norm(to_target.vector)
        
        # Determine speed based on distance
        if distance < 0.0001:
            speed = 0.0
        else:
            decel_tweaker = 0.3  # Tuning parameter for deceleration
            speed = distance / decel_tweaker
            speed = min(speed, self.max_speed)
        
        # Scale desired velocity
        desired_velocity = Position.Position3D(
            desired_direction.x * speed,
            desired_direction.y * speed,
            desired_direction.z * speed
        )
        
        # Calculate steering force
        steer = desired_velocity - self.velocity
        return truncate(steer, self.max_force)
    
    def update(self, dt: float, window_w: int, window_h: int) -> None:
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
        distance_to_target = self.position.distance_to(self.target)

        if self.action == 'seek':
            self._acceleration = self.seek()
        elif self.action == 'flee':
            if distance_to_target < 300:
                self._acceleration = self.flee()
            else:
                self._acceleration = Position.Position3D(0.0, 0.0, 0.0) # Reset acceleration
        elif self.action == 'arrive':
            self._acceleration = self.arrive()
        
        # Euler integrate
        # self._velocity = truncate(self._velocity + self._acceleration * dt, self.max_speed)
        # Position3D scalar multiplication for acceleration
        scaled_acceleration = Position.Position3D(self._acceleration.x * dt, self._acceleration.y * dt, self._acceleration.z * dt)
        self._velocity = truncate(self._velocity + scaled_acceleration, self.max_speed)
        # self.position = self.position + self.velocity * dt
        # Position3D scalar multiplication for velocity
        scaled_velocity = Position.Position3D(self._velocity.x * dt, self._velocity.y * dt, self._velocity.z * dt)
        self.position = self.position + scaled_velocity

        