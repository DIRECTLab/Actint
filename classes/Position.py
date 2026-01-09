from abc import ABC, abstractmethod
import numpy as np

def _haversine_distance_numpy(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  """
  Calculate the great circle distance between two points 
  on the earth (specified in decimal degrees)
  Returns distance in kilometers
  
  All inputs can be scalars or arrays of the same shape.
  """
  # Convert decimal degrees to radians
  lat1 = np.radians(lat1)
  lon1 = np.radians(lon1)
  lat2 = np.radians(lat2)
  lon2 = np.radians(lon2)
  
  # Haversine formula
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
  c = 2 * np.arcsin(np.sqrt(a))
  
  # Radius of earth in kilometers
  r = 6371
  
  return c * r

class Position(ABC):
  """Abstract base class for position representations."""
  
  @property
  @abstractmethod
  def vector(self) -> np.ndarray[np.float64]:
    """Return the position as a numpy array."""
    pass
  
  @abstractmethod
  def distance_to(self, position: 'Position') -> float:
    """Calculate the distance to another position."""
    pass
  
  @abstractmethod
  def get_heading(self, position: 'Position') -> float:
    """Calculate the heading (angle) to another position in radians."""
    pass
  
  def get_heading_deg(self, position: 'Position') -> float:
    return np.rad2deg(self.get_heading(position))



class Position2D(Position):
  """
  2D position representation in Cartesian coordinates.

  This class represents a point in 2D space with x and y coordinates.
  It inherits from Position and provides 2D-specific functionality.

  Example:
    >>> pos = Position2D(3.0, 4.0)
    >>> print(pos.x, pos.y)
    3.0 4.0
    
  Attributes:
    x (float): The x-coordinate of the position
    y (float): The y-coordinate of the position
  """
  
  def __init__(self, x: float, y: float):
    """
    Initialize a 2D position with x and y coordinates.
    
    Args:
      x (float): The x-coordinate
      y (float): The y-coordinate
    """
    self._vector = np.array([x, y], dtype=np.float64)


  @property
  def x(self) -> float:
    """The x-coordinate of the position."""
    return self._vector[0]

  @x.setter
  def x(self, value: float) -> None:
    self._vector[0] = value

  @property
  def y(self) -> float:
    """The y-coordinate of the position."""
    return self._vector[1]

  @y.setter
  def y(self, value: float) -> None:
    self._vector[1] = value

  @property
  def vector(self) -> np.ndarray[np.float64]:
    """Return the position as a numpy array."""
    return self._vector.copy()  # Return a copy to prevent external modification

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position. This will be used for now to imitate UTM distance with objects in the same UTM zone. As we progress we will need to update this for objects in different UTM zones.
    
    If the other position is 3D, the z component is ignored.
    If the other position is 2D, all components are considered.
    
    Args:
      position (Union[Position2D, Position3D]): Another position to calculate distance to
        
    Returns:
      float: The Euclidean distance between positions
        
    Example:
      >>> pos1 = Position2D(0, 0)
      >>> pos2 = Position2D(3, 4)
      >>> pos1.distance_to(pos2)
      5.0
    """
    if not isinstance(position, (Position2D, Position3D)):
        raise TypeError(f"Unsupported position type: {type(position).__name__}. "
                       f"Must be Position2D or Position3D")
    # If the other position is also a Position2D, ignore z components
    return np.sqrt((self.x - position.x)**2 + (self.y - position.y)**2)
  
  def get_heading(self, position: 'Position') -> float:
    """
    Calculate the heading (angle) to another position in radians.
    
    Args:
      position (Position): Another position to calculate heading to
        
    Returns:
      float: The heading in radians (0 = north, clockwise)
    """
    if isinstance(position, Position2D):
      diff = position._vector - self._vector
    else:
      raise TypeError(f"Unsupported position type: {type(position).__name__}. " f"Must be Position2D")
  
    # arctan2 gives angle from positive x-axis (counterclockwise)
    # We want angle from positive y-axis (north), clockwise
    # So we need: π/2 - angle (to convert to north-oriented)
    # But we also need to handle the clockwise convention properly
    angle = np.arctan2(diff[1], diff[0])
    # Convert to maritime convention (0° = north, clockwise)
    heading = (np.pi / 2 - angle) % (2 * np.pi)
    return heading

  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f})'
  
  def __repr__(self) -> str:
    return f'{type(self).__name__}(x={self.x}, y={self.y})'
    
  def __eq__(self, other: object) -> bool:
    """Check equality with another position."""
    if not isinstance(other, Position2D):
      return False
    return np.allclose(self._vector, other._vector)
  
  def __add__(self, other: 'Position2D') -> 'Position2D':
    """Add two positions."""
    if isinstance(other, Position2D):
      return Position2D(self.x + other.x, self.y + other.y)
    raise TypeError(f"Can only add Position2D to Position2D NOT {type(other).__name__}")
  
  def __sub__(self, other: 'Position2D') -> 'Position2D':
    """Subtract two positions."""
    if isinstance(other, Position2D):
      return Position2D(self.x - other.x, self.y - other.y)
    raise TypeError(f"Can only subtract Position2D from Position2D NOT {type(other).__name__}")


class Position3D(Position2D):
  """
  3D position representation in Cartesian coordinates.
  
  This class represents a point in 3D space with x, y, and z coordinates.
  It inherits from Position2D and adds the z coordinate functionality.
  
  Example:
      >>> pos = Position3D(1.0, 2.0, 3.0)
      >>> print(pos.x, pos.y, pos.z)
      1.0 2.0 3.0
      
  Attributes:
      x (float): The x-coordinate of the position
      y (float): The y-coordinate of the position
      z (float): The z-coordinate of the position
  """
  def __init__(self, x: float, y: float, z: float):
    """
    Initialize a 3D position with x, y, and z coordinates.
    
    Args:
        x (float): The x-coordinate
        y (float): The y-coordinate
        z (float): The z-coordinate
    """
    # Initialize the parent Position2D with x, y
    # But we need to override _vector to be 3D
    self._vector = np.array([x, y, z], dtype=np.float64)

  @property
  def z(self) -> float:
    """The z-coordinate of the position."""
    return self._vector[2]

  @z.setter
  def z(self, value: float) -> None:
    self._vector[2] = value

  @property
  def vector(self) -> np.ndarray[np.float64]:
    """Return the position as a numpy array."""
    return self._vector.copy()  # Return a copy to prevent external modification

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position.
    
    If the other position is 2D, the z component is ignored.
    If the other position is 3D, all components are considered.
    
    Args:
        position (Union[Position2D, Position3D]): Another position to calculate distance to
        
    Returns:
        float: The Euclidean distance between positions
        
    Example:
        >>> pos1 = Position3D(0, 0, 0)
        >>> pos2 = Position3D(1, 1, 1)
        >>> pos1.distance_to(pos2)
        1.7320508075688772
    """
    # If the other position is a Position2D, ignore z components
    if not isinstance(position, (Position2D, Position3D)):
        raise TypeError(f"Unsupported position type: {type(position).__name__}. "
                       f"Must be Position2D or Position3D")
    
    if isinstance(position, Position2D) and not isinstance(position, Position3D):
        # Other position is 2D only, ignore z component
        return np.sqrt((self.x - position.x)**2 + (self.y - position.y)**2)
    else:
        # Other position is 3D, use all components
        return np.sqrt((self.x - position.x)**2 + (self.y - position.y)**2 + (self.z - position.z)**2)
  
  def get_direction_vector(self, position: 'Position') -> 'Position3D':
    """
    Get a normalized 3D direction vector to another position.
    
    Calculates both heading (horizontal direction) and pitch (vertical angle)
    and combines them into a single 3D unit direction vector.
    
    Args:
      position (Position): Another position to calculate direction to
        
    Returns:
      Position3D: A normalized unit direction vector pointing to the target
      
    Example:
      >>> pos1 = Position3D(0, 0, 0)
      >>> pos2 = Position3D(10, 0, 5)
      >>> direction = pos1.get_direction_vector(pos2)
      >>> # direction is a unit vector pointing towards pos2
    """
    if not isinstance(position, (Position2D, Position3D)):
      raise TypeError(f"Unsupported position type: {type(position).__name__}. " f"Must be Position2D or Position3D")
    
    # Calculate differences
    diff_x = position.x - self.x
    diff_y = position.y - self.y
    diff_z = position.z - self.z if isinstance(position, Position3D) else 0
    
    # Calculate horizontal distance in x-y plane
    horizontal_dist = np.sqrt(diff_x**2 + diff_y**2)
    
    # Calculate heading in x-y plane
    # arctan2 gives angle from positive x-axis (counterclockwise)
    # We want angle from positive y-axis (north), clockwise
    angle = np.arctan2(diff_y, diff_x)
    heading = (np.pi / 2 - angle) % (2 * np.pi)
    
    # Calculate pitch (elevation angle)
    pitch = np.arctan2(diff_z, horizontal_dist)
    
    # Convert angles to 3D Cartesian coordinates
    # heading: 0 = north (positive y), π/2 = east (positive x), π = south, 3π/2 = west
    # pitch: 0 = horizontal, positive = upward, negative = downward
    
    # Horizontal magnitude reduces as pitch increases
    horizontal_mag = np.cos(pitch)
    
    # Calculate direction components
    direction_x = np.sin(heading) * horizontal_mag
    direction_y = np.cos(heading) * horizontal_mag
    direction_z = np.sin(pitch)
    
    # Normalize to unit vector
    magnitude = np.sqrt(direction_x**2 + direction_y**2 + direction_z**2)
    if magnitude > 1e-9:
      return Position3D(
        float(direction_x / magnitude),
        float(direction_y / magnitude),
        float(direction_z / magnitude)
      )
    else:
      return Position3D(0.0, 0.0, 0.0)

  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f}, {self.z:.2f})'
  
  def __repr__(self) -> str:
    return f'{type(self).__name__}(x={self.x}, y={self.y}, z={self.z})'
    
  def __eq__(self, other: object) -> bool:
    """Check equality with another position."""
    if not isinstance(other, Position3D):
      return False
    return np.allclose(self._vector, other._vector)
  
  def __add__(self, other: 'Position3D') -> 'Position3D':
    """Add two positions."""
    if isinstance(other, Position3D):
      return Position3D(self.x + other.x, self.y + other.y, self.z + other.z)
    raise TypeError(f"Can only add Position3D to Position3D NOT {type(other).__name__}")
  
  def __sub__(self, other: 'Position3D') -> 'Position3D':
    """Subtract two positions."""
    if isinstance(other, Position3D):
      return Position3D(self.x - other.x, self.y - other.y, self.z - other.z)
    raise TypeError(f"Can only subtract Position3D from Position3D NOT {type(other).__name__}")
  
  
class Position2DGCS(Position):
  """
  2D position representation in Cartesian coordinates.

  This class represents a point in 2D space with x and y coordinates.
  It inherits from Position and provides 2D-specific functionality.

  Example:
      >>> pos = Position2D(41.74076, -111.81404)
      >>> print(pos.x, pos.y)
      41.74076, -111.81404
      
  Attributes:
      x (float): The longitude of the position
      y (float): The latitude of the position
  """
  
  def __init__(
      self,
      longitude: float,
      latitude: float
  ):
    """
    Initialize a 2D position with x and y coordinates.
    
    Args:
        longitude (float): The x-coordinate
        latitude (float): The y-coordinate
    """
    self._x = longitude
    self._y = latitude

  @property
  def x(self) -> float:
     return self._x
  
  @property
  def y(self) -> float:
     return self._y
  
  @property
  def latitude(self) -> float:
     return self._x
  
  @property
  def longitude(self) -> float:
     return self._y
  
  @property
  def x(self, value: float):
     self._x = value
  
  @property
  def y(self, value: float):
     self._y = value
  
  @property
  def latitude(self, value: float):
     self._x = value
  
  @property
  def longitude(self, value: float):
     self._y = value

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position.
    
    If the other position is 3D, the z component is ignored.
    If the other position is 2D, all components are considered.
    
    Args:
        position (Union[Position2D, Position3D]): Another position to calculate distance to
        
    Returns:
        float: The Euclidean distance between positions
        
    Example:
        >>> pos1 = Position2D(0, 0)
        >>> pos2 = Position2D(3, 4)
        >>> pos1.distance_to(pos2)
        5.0
    """
    if not isinstance(position, (Position2DGCS, Position3DGCS)):
        raise TypeError(f"Unsupported position type: {type(position).__name__}. "
                       f"Must be Position2DGCS or Position3DGCS")
    # If the other position is also a Position2D, ignore z components
    return _haversine_distance_numpy(self.latitude, self.longitude, position.latitude, position.longitude)
  
  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f})'


class Position3DGCS(Position2DGCS):
  """
  3D position representation in Cartesian coordinates.
  
  This class represents a point in 3D space with x, y, and z coordinates.
  It inherits from Position2D and adds the z coordinate functionality.
  
  Example:
      >>> pos = Position3D(1.0, 2.0, 3.0)
      >>> print(pos.x, pos.y, pos.z)
      1.0 2.0 3.0
      
  Attributes:
      x (float): The x-coordinate of the position
      y (float): The y-coordinate of the position
      z (float): The z-coordinate of the position
  """
  def __init__(self, 
      longitude: float,
      latitude: float, 
      altitude: float):
    """
    Initialize a 3D position with x, y, and z coordinates.
    
    Args:
        x (float): The x-coordinate
        y (float): The y-coordinate
        z (float): The z-coordinate
    """
    super().__init__(longitude, latitude)
    self._z = altitude

  @property
  def altitude(self) -> float:
     return self._z
  
  @property
  def z(self, value: float):
     self._z = value

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position.
    
    If the other position is 2D, the z component is ignored.
    If the other position is 3D, all components are considered.
    
    Args:
        position (Union[Position2D, Position3D]): Another position to calculate distance to
        
    Returns:
        float: The Euclidean distance between positions
        
    Example:
        >>> pos1 = Position3D(0, 0, 0)
        >>> pos2 = Position3D(1, 1, 1)
        >>> pos1.distance_to(pos2)
        1.7320508075688772
    """
    # If the other position is a Position2D, ignore z components
    if not isinstance(position, (Position2DGCS, Position3DGCS)):
        raise TypeError(f"Unsupported position type: {type(position).__name__}. "
                       f"Must be Position2D or Position3D")
    
    horizonal_diff = super().distance_to(position)

    if isinstance(position, Position2DGCS):
        return horizonal_diff
    else:
       #TODO
       pass


  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f}, {self.z:.2f})'