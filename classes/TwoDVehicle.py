import queue, math, numpy, random
import pyglet.shapes as shapes
from classes import Vehicle, Position

# Helper functions adapted to use Position2D
def normalize(v: Position.Position2D) -> Position.Position2D:
    # Access the underlying numpy array for calculation
    v_vec = v.vector
    norm = numpy.linalg.norm(v_vec)
    if norm > 1e-9:
        normalized_vec = v_vec / norm
        return Position.Position2D(float(normalized_vec[0]), float(normalized_vec[1]))
    return Position.Position2D(0.0, 0.0)

def truncate(v: Position.Position2D, lim: float) -> Position.Position2D:
    # Access the underlying numpy array for calculation
    v_vec = v.vector
    n = numpy.linalg.norm(v_vec)
    if n > lim:
        truncated_vec = v_vec * (lim / n)
        return Position.Position2D(float(truncated_vec[0]), float(truncated_vec[1]))
    return v


class Vehicle2D(Vehicle):
    def __init__(self,
                 position: Position.Position2D,
                 vehicle_type: str,
                 vehicle_id: int,
                 destination_queue: queue.Queue,

                 velocity_x: float = 0.0,
                 velocity_y: float = 0.0,
                 mass: float = 1.0,
                 max_speed: float = 100.0,
                 max_force: float = 200.0,
                 scale: float = 10.0,
                 max_turn_rate: float = math.pi,
                 ):
        super().__init__(vehicle_type,
                         vehicle_id,
                         destination_queue,
                         )
        self.position: Position.Position2D = position
        self._velocity: Position.Position2D = Position.Position2D(velocity_x, velocity_y)
        self._acceleration: Position.Position2D = Position.Position2D(0.0, 0.0)
        self.mass: numpy.float64 = numpy.float64(mass)
        self.max_speed: numpy.float64 = numpy.float64(max_speed)
        self.max_force: numpy.float64 = numpy.float64(max_force)
        self.max_turn_rate: numpy.float64 = numpy.float64(max_turn_rate)
        self.heading: numpy.float64 = numpy.float64(0.0)
        self.scale: float = scale
        self.vertices = self._build_arrow()
        self.target = Position.Position2D(0.0, 0.0)
        self.action = 'none'
        # Inherited from Vehicle:
        # self.next_destination: Destination = None


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
    def velocity(self) -> Position.Position2D:
        return Position.Position2D(self._velocity.x, self._velocity.y)

    @velocity.setter
    def velocity(self, velocity: Position.Position2D) -> None:
        self._velocity = Position.Position2D(velocity.x, velocity.y)

    @property
    def acceleration_x(self) -> float:
        return self._acceleration.x

    @property
    def acceleration_y(self) -> float:
        return self._acceleration.y

    @property
    def acceleration(self) -> Position.Position2D:
        return Position.Position2D(self._acceleration.x, self._acceleration.y)

    @acceleration.setter
    def acceleration(self, acceleration: Position.Position2D) -> None:
        self._acceleration = Position.Position2D(acceleration.x, acceleration.y)

    def _build_arrow(self) -> numpy.NDArray[numpy.float64]:
        return numpy.array([
            [1, 0],
            [-1, 0.5],
            [-0.5, 0],
            [-1, -0.5]
        ], dtype=numpy.float64) * self.scale

    def seek(self) -> Position.Position2D:
        desired_direction = normalize(self.target - self.position)
        # Scalar multiplication for Position2D
        desired_velocity = Position.Position2D(
            desired_direction.x * self.max_speed,
            desired_direction.y * self.max_speed
        )
        steer = desired_velocity - self.velocity
        return truncate(steer, self.max_force)
    
    def flee(self) -> Position.Position2D:
        desired_direction = normalize(self.target - self.position)
        # Scalar multiplication for Position2D
        desired_velocity = Position.Position2D(
            desired_direction.x * self.max_speed,
            desired_direction.y * self.max_speed
        )
        # Negate desired_velocity for flee behavior
        desired_velocity = Position.Position2D(-desired_velocity.x, -desired_velocity.y)
        steer = desired_velocity - self.velocity
        return truncate(steer, self.max_force)
    
    def arrive(self) -> Position.Position2D:
        # Calculate the vector from the vehicle's current position to the target
        to_target = self.target - self.position

        # Calculate the distance to the target
        distance = to_target.distance_to(Position.Position2D(0.0, 0.0)) # Distance of the to_target vector

        # If the vehicle is very close to the target, it should stop
        if distance < 1: # A small threshold to prevent division by zero and ensure full stop
            self.target = Position.Position2D(random.randrange(0, 800), random.randrange(0, 800))
            return Position.Position2D(0.0, 0.0) # Return zero force

        # Calculate the desired speed based on the distance
        desired_speed: float

        if distance < 3:
                desired_speed = 0.01

        elif distance < 200:
            # Inside the slowing radius, linearly interpolate speed
            # Speed will be max_speed at deceleration_radius and 0 at distance 0
            desired_speed = self.max_speed * (distance / 200)
        else:
            # Outside the slowing radius, go at max speed
            desired_speed = self.max_speed

        # Calculate the desired velocity
        # First, normalize the 'to_target' vector to get the direction
        desired_direction = normalize(to_target)
        # Then, multiply by the desired_speed
        desired_velocity = Position.Position2D(
            desired_direction.x * desired_speed,
            desired_direction.y * desired_speed
        )

        # Calculate the steering force
        steer = desired_velocity - self.velocity

        # Truncate the steering force to max_force
        return truncate(steer, self.max_force)

    def update(self, dt: float, window_w: int, window_h: int) -> None:
        distance_to_target = self.position.distance_to(self.target)

        if self.action == 'seek':
            self._acceleration = self.seek()
        elif self.action == 'flee':
            if distance_to_target < 300:
                self._acceleration = self.flee()
            else:
                self._acceleration = Position.Position2D(0.0, 0.0) # Reset acceleration
        elif self.action == 'arrive':
            self._acceleration = self.arrive()

        # Euler integrate
        # self._velocity = truncate(self._velocity + self._acceleration * dt, self.max_speed)
        # Position2D scalar multiplication for acceleration
        scaled_acceleration = Position.Position2D(self._acceleration.x * dt, self._acceleration.y * dt)
        self._velocity = truncate(self._velocity + scaled_acceleration, self.max_speed)

        # self.position = self.position + self.velocity * dt
        # Position2D scalar multiplication for velocity
        scaled_velocity = Position.Position2D(self._velocity.x * dt, self._velocity.y * dt)
        self.position = self.position + scaled_velocity

        # Update heading from velocity
        if self._velocity.distance_to(Position.Position2D(0, 0)) > 1e-6:
            self.heading = math.atan2(self._velocity.y, self._velocity.x)

        # Wrap around screen edges
        self.position.x = self.position.x % window_w
        self.position.y = self.position.y % window_h

    def draw(self):
        # Access the underlying numpy array for drawing transformations
        current_pos_array = self.position.vector

        c, s = math.cos(self.heading), math.sin(self.heading)
        rot_matrix = numpy.array([[c, -s], [s, c]], dtype=numpy.float64)

        transformed_pts = (rot_matrix @ self.vertices.T).T + current_pos_array

        coords_for_drawing = [(float(p[0]), float(p[1])) for p in transformed_pts]

        for i in range(len(coords_for_drawing)):
            start_x, start_y = coords_for_drawing[i]
            end_x, end_y = coords_for_drawing[(i + 1) % len(coords_for_drawing)]
            shapes.Line(start_x, start_y, end_x, end_y, color=(0, 200, 255)).draw()