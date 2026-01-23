import queue, math, random
import numpy as np
from numpy.typing import NDArray
import pyglet
from .Vehicle import Vehicle
from .Position import Position2D

# Helper functions adapted to use Position2D
def normalize(v: Position2D) -> Position2D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        return Position2D(*[float(x) for x in vec / norm])
    return Position2D(0.0, 0.0)

def truncate(v: Position2D, limit: float) -> Position2D:
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > limit:
        scaled = vec * (limit / norm)
        return Position2D(*[float(x) for x in scaled])
    return v

def scale_position(pos: Position2D, scalar: float) -> Position2D:
    """Scale a position/velocity vector by a scalar."""
    return Position2D(pos.x * scalar, pos.y * scalar)

class Vehicle2D(Vehicle):
    def __init__(
            self,
            vehicle_id: int,
            vehicle_type: str,
            destination_queue: queue.Queue,
            time_step: float = 1,
            
            position: Position2D = Position2D(0,0),
            max_speed: float = 100.0,
            max_force: float = 200.0,
            scale: float = 10.0,
            ):
        super().__init__(
            vehicle_id,
            vehicle_type,
            destination_queue,
            time_step,
            )
        self.position: Position2D = position
        self._velocity: Position2D = Position2D(0.0, 0.0)
        self._acceleration: Position2D = Position2D(0.0, 0.0)
        self.max_speed: np.float64 = np.float64(max_speed)
        self.max_force: np.float64 = np.float64(max_force)
        self.heading: np.float64 = np.float64(0.0)
        self.scale: float = scale
        self.vertices = self._build_arrow()
        self.target: Position2D = Position2D(0.0, 0.0)
        # Inherited from Vehicle:
        # self.next_destination: Destination = None
        # self.done : bool = False


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
    def velocity(self) -> Position2D:
        return Position2D(self._velocity.x, self._velocity.y)

    @velocity.setter
    def velocity(self, velocity: Position2D) -> None:
        self._velocity = Position2D(velocity.x, velocity.y)

    @property
    def acceleration_x(self) -> float:
        return self._acceleration.x

    @property
    def acceleration_y(self) -> float:
        return self._acceleration.y

    @property
    def acceleration(self) -> Position2D:
        return Position2D(self._acceleration.x, self._acceleration.y)

    @acceleration.setter
    def acceleration(self, acceleration: Position2D) -> None:
        self._acceleration = Position2D(acceleration.x, acceleration.y)

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

    def seek(self) -> Position2D:
        desired_direction = normalize(self.target - self.position)
        desired_velocity = scale_position(desired_direction, min(self.max_speed, self.target_speed()))
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def flee(self) -> Position2D:
        desired_direction = normalize(self.target - self.position)
        desired_velocity = scale_position(desired_direction, -min(self.max_speed, self.target_speed()))
        return truncate(desired_velocity - self.velocity, self.max_force)
    
    def arrive(self) -> Position2D:
        # Calculate the vector from the vehicle's current position to the target
        to_target = self.target - self.position

        # Calculate the distance to the target
        distance = np.linalg.norm(to_target.vector)

        # If the vehicle is very close to the target, it should stop
        if distance < 1: # A small threshold to prevent division by zero and ensure full stop
            self.target = Position2D(random.randrange(0, 800), random.randrange(0, 800))
            return Position2D(0.0, 0.0) # Return zero force

        # Calculate the desired speed based on the distance
        if distance < 3:
            desired_speed = 0.01
        elif distance < 200:
            desired_speed = min(self.max_speed, self.target_speed()) * (distance / 200)
        else:
            desired_speed = min(self.max_speed, self.target_speed())

        # Calculate the desired velocity
        # First, normalize the 'to_target' vector to get the direction
        desired_direction = normalize(to_target)
        # Then, multiply by the desired_speed
        desired_velocity = scale_position(desired_direction, desired_speed)
        return truncate(desired_velocity - self.velocity, self.max_force)

    def update(self, dt: float, window_w: int, window_h: int) -> None:
        """
        Update the vehicle's position and state. Does nothing if there is no current or next destination.
        """
        if self.done:
            return
        if self.next_destination is None:
            if self._has_next_destination():
                self._assign_next_destination()
            else: 
                self.done = True
                return

        if self.next_destination.action == 'seek':
            self._acceleration = self.seek()
        elif self.next_destination.action == 'flee':
            distance_to_target = self.position.distance_to(self.target)
            if distance_to_target < 300:
                self.acceleration = self.flee()
            else:
                self.acceleration = Position2D(0.0, 0.0)
        elif self.next_destination.action == 'arrive':
            self._acceleration = self.arrive()
        else:
            self.done = True
            self._acceleration = Position2D(0.0, 0.0)

        self._velocity = truncate(self._velocity + scale_position(self._acceleration, dt), self.max_speed)
        self.position = self.position + scale_position(self._velocity, dt)

        if self._velocity.distance_to(Position2D(0, 0)) > 1e-6:
            self.heading = math.atan2(self._velocity.y, self._velocity.x)

        self.pos_x = self.pos_x % window_w
        self.pos_y = self.pos_y % window_h

        if self.next_destination.has_reached(self.position):
            if self._has_next_destination():
                self._assign_next_destination()
            else:
                self.done = True
                return

    # def draw(self):
    #     # Access the underlying numpy array for drawing transformations
    #     current_pos_array = self.position.vector

    #     c, s = math.cos(self.heading), math.sin(self.heading)
    #     rot_matrix = np.array([[c, -s], [s, c]], dtype=np.float64)

    #     transformed_pts = (rot_matrix @ self.vertices.T).T + current_pos_array

    #     coords_for_drawing = [(float(p[0]), float(p[1])) for p in transformed_pts]

    #     for i in range(len(coords_for_drawing)):
    #         start_x, start_y = coords_for_drawing[i]
    #         end_x, end_y = coords_for_drawing[(i + 1) % len(coords_for_drawing)]
    #         pyglet.graphics.draw(
    #             2,
    #             pyglet.gl.GL_LINES,
    #             ('v2f', [start_x, start_y, end_x, end_y]),
    #             ('c3B', [0, 200, 255, 0, 200, 255])
    #         )
