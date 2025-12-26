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
  @abstractmethod
  def distance_to(self, position: 'Position') -> float:
    """
    Calculate the distance to another position.
    
    Args:
        position (Position): Another position object to calculate distance to
        
    Returns:
        float: The distance between this position and the other position
        
    Raises:
        NotImplementedError: This method must be implemented by subclasses
    """
    raise NotImplementedError("This method is abstract ands hould be written.")
  
  @abstractmethod
  def get_heading(self, position: 'Position') -> float:
    raise NotImplementedError("This method is abstract ands hould be written.")




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
  
  def __init__(
      self,
      x: float,
      y: float
  ):
    """
    Initialize a 2D position with x and y coordinates.
    
    Args:
        x (float): The x-coordinate
        y (float): The y-coordinate
    """
    self.x = x
    self.y = y

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
    if not isinstance(position, (Position2D, Position3D)):
        raise TypeError(f"Unsupported position type: {type(position).__name__}. "
                       f"Must be Position2D or Position3D")
    # If the other position is also a Position2D, ignore z components
    return np.sqrt((self.x - position.x)**2 + (self.y - position.y)**2)
  
  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f})'
  
  def get_heading(self, position: 'Position') -> float:
    raise NotImplementedError("This method should be written.")

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
    super().__init__(x, y)
    self.z = z

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
    
    if isinstance(position, Position2D):
        return super().distance_to(position)
    else:
        return np.linalg.norm([self.x, self.y, self.z] - [position.x, position.y, position.z])
    
  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f}, {self.z:.2f})'
  
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