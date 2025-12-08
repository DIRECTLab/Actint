from abc import ABC, abstractmethod
import numpy as np

class Position(ABC):
  @abstractmethod
  def distance_to(self, position: 'Position') -> float:
    """
    Calculate the Euclidean distance to another position.
    
    Args:
        position (Position): Another position object to calculate distance to
        
    Returns:
        float: The Euclidean distance between this position and the other position
        
    Raises:
        NotImplementedError: This method must be implemented by subclasses
    """
    pass

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
    return np.sqrt(np.dot(self.x - position.x, self.y - position.y))
  
  def __str__(self):
    return f'Position2D({self.x:.2f}, {self.y:.2f})'


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
    return f'Position3D({self.x:.2f}, {self.y:.2f}, {self.z:.2f})'