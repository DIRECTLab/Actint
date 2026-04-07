from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
from numpy.typing import NDArray
from .Vectors import Vector2D, Vector3D
from pyproj import Geod
from helpers import utm

geod = Geod(ellps='WGS84')

class Position(ABC):
  """Abstract base class for position representations."""
  
  @property
  @abstractmethod
  def vector(self) -> NDArray[np.float64]:
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

  # Removed abstract methods for __add__, __sub__, etc. from Position ABC
  # as they don't apply universally to all Position types (e.g., Lat/Lon).
  # They will be implemented in Cartesian-like classes (PositionUTM, Position3D).
  
  @abstractmethod
  def __eq__(self, other: object) -> bool:
      pass

  # Common vector operations that apply *only* to Cartesian positions (PositionUTM, Position3D)
  # These should ideally be moved out of the base `Position` class,
  # or `Position` should represent a vector-like entity.
  # For now, let's keep them here but understand they will be overridden
  # or only applicable for PositionUTM/3D.
  def magnitude(self) -> float:
      return np.linalg.norm(self.vector)

  def normalize(self) -> 'Position':
      norm = self.magnitude()
      if norm > 1e-9:
          return self / norm
      # Return a zero vector of the same type, assuming Position sub-classes
      # implement __mul__ for scalar multiplication correctly.
      return self * 0.0 # Will call __mul__ if implemented in concrete class

  def truncate(self, limit: float) -> 'Position':
      norm = self.magnitude()
      if norm > limit:
          return self.normalize() * limit
      return self


class PositionUTM(Position): # This is now exclusively for Cartesian/UTM (easting, northing)
  """
  2D position representation in Cartesian coordinates (e.g., UTM easting/northing).

  This class represents a point in 2D space with x and y coordinates.
  It inherits from Position and provides 2D-specific functionality.

  Attributes:
    x (float): The x-coordinate (easting)
    y (float): The y-coordinate (northing)
  """
  
  def __init__(self, x: float, y: float, utm_zone_number: int = None, utm_zone_letter: str = None):
    self._vector = np.array([float(x), float(y)], dtype=np.float64)
    self._utm_zone_number = utm_zone_number
    self._utm_zone_letter = utm_zone_letter

  @property
  def x(self) -> float:
    """The x-coordinate of the position (easting)."""
    return self._vector[0]

  @x.setter
  def x(self, value: float) -> None:
    self._vector[0] = float(value)

  @property
  def y(self) -> float:
    """The y-coordinate of the position (northing)."""
    return self._vector[1]

  @y.setter
  def y(self, value: float) -> None:
    self._vector[1] = float(value)

  @property
  def number(self) -> int:
    """The UTM zone number."""
    return self._utm_zone_number
  
  @number.setter
  def number(self, value: int) -> None:
    self._utm_zone_number = int(value)
  
  @property
  def letter(self) -> str:
    """The UTM zone letter."""
    return self._utm_zone_letter
  
  @letter.setter
  def letter(self, value: str) -> None:
    self._utm_zone_letter = str(value)

  @property
  def vector(self) -> NDArray[np.float64]:
    """Return the position as a numpy array."""
    return self._vector.copy()  # Return a copy to prevent external modification

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position.
    This is used for local movement within the same UTM zone.
    
    Args:
      position (Position): Another position to calculate distance to.
                           Expected to be PositionUTM or Position3D.
        
    Returns:
      float: The Euclidean distance between positions in meters.
    """
    if not isinstance(position, (PositionUTM, Position3D)):
        raise TypeError(f"Unsupported position type for Euclidean distance: {type(position).__name__}. "
                       f"Must be PositionUTM or Position3D")
    
    # Ensure compatible dimensions for distance calculation
    other_vec = position.vector
    if len(other_vec) < 2:
        raise ValueError("Cannot calculate 2D Euclidean distance to a 1D or lower dimension position.")
    
    return np.linalg.norm(self._vector - other_vec[:2])

  def get_heading(self, position: 'Position') -> float:
    """
    Calculate the heading (angle) to another position in radians.
    (0 = positive x-axis, counter-clockwise in a standard Cartesian plane)
    
    Args:
      position (Position): Another position to calculate heading to
        
    Returns:
      float: The heading in radians.
    """
    if not isinstance(position, (PositionUTM, Position3D)):
      raise TypeError(f"Unsupported position type for heading calculation: {type(position).__name__}. " f"Must be PositionUTM or Position3D")
  
    diff_vector = position.vector[:2] - self._vector
    return np.arctan2(diff_vector[1], diff_vector[0])

  def __str__(self):
    return f'{type(self).__name__}({self.x:.2f}, {self.y:.2f}, {self._utm_zone_number}{self._utm_zone_letter})'
  
  def __repr__(self) -> str:
    return f'{type(self).__name__}(x={self.x}, y={self.y}, utm_zone_number={self._utm_zone_number}, utm_zone_letter={self._utm_zone_letter})'

  def __eq__(self, other: object) -> bool:
    """Check equality with another position."""
    if not isinstance(other, PositionUTM):
      return False
    return np.allclose(self._vector, other._vector, atol=1e-9)
  
  def __add__(self, other: PositionUTM | Vector2D) -> PositionUTM:
    """Add two positions."""
    if isinstance(other, PositionUTM):
      if (
          self._utm_zone_number is not None
          and other._utm_zone_number is not None
          and (
              self._utm_zone_number != other._utm_zone_number
              or self._utm_zone_letter != other._utm_zone_letter
          )
      ):
        raise ValueError(
            "Cannot add PositionUTM values from different UTM zones: "
            f"{self._utm_zone_number}{self._utm_zone_letter} vs {other._utm_zone_number}{other._utm_zone_letter}"
        )
      return PositionUTM(
          self.x + other.x,
          self.y + other.y,
          utm_zone_number=self._utm_zone_number or other._utm_zone_number,
          utm_zone_letter=self._utm_zone_letter or other._utm_zone_letter,
      )
    if isinstance(other, Vector2D):
      return PositionUTM(
          self.x + other.x,
          self.y + other.y,
          utm_zone_number=self._utm_zone_number,
          utm_zone_letter=self._utm_zone_letter,
      )
    raise TypeError(f"Can only add PositionUTM to PositionUTM NOT {type(other).__name__}")

  def __sub__(self, other: PositionUTM | Vector2D) -> PositionUTM:
    """Subtract two positions."""
    if isinstance(other, PositionUTM):
      if (
          self._utm_zone_number is not None
          and other._utm_zone_number is not None
          and (
              self._utm_zone_number != other._utm_zone_number
              or self._utm_zone_letter != other._utm_zone_letter
          )
      ):
        raise ValueError(
            "Cannot subtract PositionUTM values from different UTM zones: "
            f"{self._utm_zone_number}{self._utm_zone_letter} vs {other._utm_zone_number}{other._utm_zone_letter}"
        )
      return PositionUTM(
          self.x - other.x,
          self.y - other.y,
          utm_zone_number=self._utm_zone_number or other._utm_zone_number,
          utm_zone_letter=self._utm_zone_letter or other._utm_zone_letter,
      )
    if isinstance(other, Vector2D):
      return PositionUTM(
          self.x - other.x,
          self.y - other.y,
          utm_zone_number=self._utm_zone_number,
          utm_zone_letter=self._utm_zone_letter,
      )
    raise TypeError(f"Can only subtract PositionUTM from PositionUTM NOT {type(other).__name__}")

  def __mul__(self, scalar: float) -> 'PositionUTM':
      return PositionUTM(
        self.x * scalar,
        self.y * scalar,
        utm_zone_number=self._utm_zone_number,
        utm_zone_letter=self._utm_zone_letter,
      )

  def __rmul__(self, scalar: float) -> 'PositionUTM':
      return self.__mul__(scalar) # Scalar multiplication is commutative

  def __truediv__(self, scalar: float) -> 'PositionUTM':
      if scalar == 0:
          raise ValueError("Cannot divide PositionUTM by zero.")
      return PositionUTM(
        self.x / scalar,
        self.y / scalar,
        utm_zone_number=self._utm_zone_number,
        utm_zone_letter=self._utm_zone_letter,
      )


class Position3D(PositionUTM): # This would be for 3D Cartesian UTM (easting, northing, altitude)
  """
  3D position representation in Cartesian coordinates (e.g., UTM easting/northing/altitude).
  
  This class represents a point in 3D space with x, y, and z coordinates.
  It inherits from PositionUTM and adds the z coordinate functionality.
  
  Attributes:
      x (float): The x-coordinate (easting)
      y (float): The y-coordinate (northing)
      z (float): The z-coordinate (altitude in meters)
  """
  def __init__(self, x: float, y: float, z: float):
    self._vector = np.array([float(x), float(y), float(z)], dtype=np.float64)

  @property
  def z(self) -> float:
    """The z-coordinate of the position (altitude)."""
    return self._vector[2]

  @z.setter
  def z(self, value: float) -> None:
    self._vector[2] = float(value)

  @property
  def vector(self) -> NDArray[np.float64]:
    """Return the position as a numpy array."""
    return self._vector.copy()  # Return a copy to prevent external modification

  def distance_to(self, position: Position) -> float:
    """
    Calculate the Euclidean distance to another position.
    
    Args:
        position (Position): Another position to calculate distance to.
        
    Returns:
        float: The Euclidean distance between positions in meters.
    """
    if not isinstance(position, (PositionUTM, Position3D)):
        raise TypeError(f"Unsupported position type for Euclidean distance: {type(position).__name__}. "
                       f"Must be PositionUTM or Position3D")
    
    other_vector = position.vector
    # Pad 2D vector to 3D for consistent calculation if comparing with PositionUTM
    if len(other_vector) == 2:
        other_vector = np.append(other_vector, 0.0) # Assume Z is 0 if other is 2D
    
    return np.linalg.norm(self._vector - other_vector)
  
  def get_heading(self, position: 'Position') -> float:
    """
    Calculate the horizontal heading (angle in x-y plane) to another position in radians.
    
    Args:
      position (Position): Another position to calculate heading to
        
    Returns:
      float: The horizontal heading in radians.
    """
    if not isinstance(position, (PositionUTM, Position3D)):
      raise TypeError(f"Unsupported position type for heading calculation: {type(position).__name__}. " f"Must be PositionUTM or Position3D")
    
    diff_vector_xy = position.vector[:2] - self._vector[:2]
    return np.arctan2(diff_vector_xy[1], diff_vector_xy[0])

  def get_direction_vector(self, position: 'Position') -> 'Position3D':
    """
    Get a normalized 3D direction vector to another position.
    
    Calculates both horizontal direction and vertical angle
    and combines them into a single 3D unit direction vector.
    
    Args:
      position (Position): Another position to calculate direction to
        
    Returns:
      Position3D: A normalized unit direction vector pointing to the target
    """
    if not isinstance(position, (PositionUTM, Position3D)):
      raise TypeError(f"Unsupported position type: {type(position).__name__}. " f"Must be PositionUTM or Position3D")
    
    target_vector = position.vector
    # Pad 2D target to 3D for consistent calculation if target is PositionUTM
    if len(target_vector) == 2:
        target_vector = np.append(target_vector, 0.0)
    
    diff_vector = target_vector - self._vector
    magnitude = np.linalg.norm(diff_vector)
    
    if magnitude > 1e-9:
      normalized_diff = diff_vector / magnitude
      return Position3D(
        float(normalized_diff[0]),
        float(normalized_diff[1]),
        float(normalized_diff[2])
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
    return np.allclose(self._vector, other._vector, atol=1e-9)
  
  def __add__(self, other: 'Position3D | Vector3D') -> 'Position3D':
    """Add a 3D position and a 3D offset (vector)."""
    if isinstance(other, (Position3D, Vector3D)):
      return Position3D(self.x + other.x, self.y + other.y, self.z + other.z)
    raise TypeError(
      f"Can only add Position3D to Position3D/Vector3D NOT {type(other).__name__}"
    )
  
  def __sub__(self, other: 'Position3D | Vector3D') -> 'Position3D':
    """Subtract a 3D position/offset from this position."""
    if isinstance(other, (Position3D, Vector3D)):
      return Position3D(self.x - other.x, self.y - other.y, self.z - other.z)
    raise TypeError(
      f"Can only subtract Position3D/Vector3D from Position3D NOT {type(other).__name__}"
    )
  
  
class PositionLatLon(Position):
  """
  Position representation using Latitude and Longitude (Geographic Coordinates).
  
  Attributes:
      latitude (float): The latitude in decimal degrees.
      longitude (float): The longitude in decimal degrees.
  """
  
  def __init__(self, latitude: float, longitude: float):
    self._latitude = float(latitude)
    self._longitude = float(longitude)

  @property
  def latitude(self) -> float:
     return self._latitude
  
  @latitude.setter
  def latitude(self, value: float) -> None:
      self._latitude = float(value)
  
  @property
  def longitude(self) -> float:
     return self._longitude
  
  @longitude.setter
  def longitude(self, value: float) -> None:
      self._longitude = float(value)

  @property
  def vector(self) -> NDArray[np.float64]:
    """Returns [latitude, longitude] as a numpy array."""
    return np.array([self._latitude, self._longitude], dtype=np.float64)

  def distance_to(self, position: Position) -> float:
    """
    Calculate the geodesic distance (great-circle) to another geographic position.
    
    Args:
        position (Position): Another position, expected to be PositionLatLon.
        
    Returns:
        float: The geodesic distance between positions in *meters*.
    """
    if not isinstance(position, PositionLatLon):
        raise TypeError(f"Unsupported position type for geodesic distance: {type(position).__name__}. "
                       f"Must be PositionLatLon")
    
    distance =utm.latlon_dist(self, position)
    return distance # returns distance in meters

  def get_heading(self, position: 'Position') -> float:
    """
    Calculate the initial bearing (heading) to another geographic position in radians.
    
    Args:
      position (Position): Another position, expected to be PositionLatLon.
        
    Returns:
      float: The initial bearing in radians (0 = North, increasing clockwise).
    """
    if not isinstance(position, PositionUTM):
      raise TypeError(f"Unsupported position type for heading calculation: {type(position).__name__}. " f"Must be PositionLatLon")
    
    # geod.inv returns (azimuth1, azimuth2, distance)
    azimuth1, _, _ = geod.inv(
        self.longitude, self.latitude,
        position.longitude, position.latitude
    )
    # Convert azimuth from degrees (pyproj default) to radians
    return np.radians(azimuth1)

  def __str__(self):
    return f'{type(self).__name__}(lat={self.latitude:.5f}, lon={self.longitude:.5f})'
  
  def __repr__(self) -> str:
    return f'{type(self).__name__}(latitude={self.latitude}, longitude={self.longitude})'
    
  def __eq__(self, other: object) -> bool:
    """Check equality with another position."""
    if not isinstance(other, PositionUTM):
      return False
    return np.allclose(self.latitude, other.latitude, atol=1e-9) and \
           np.allclose(self.longitude, other.longitude, atol=1e-9)

  # Geographic coordinates do not typically support direct vector addition/subtraction
  # or scalar multiplication in the same way Cartesian coordinates do for movement.
  # So, these are explicitly not implemented for PositionLatLon.
  def __add__(self, other: 'Position') -> 'Position':
      raise NotImplementedError("Vector addition is not directly supported for PositionUTM. Use movement functions or convert to Cartesian.")
  def __sub__(self, other: 'Position') -> 'Position':
      raise NotImplementedError("Vector subtraction is not directly supported for PositionUTM. Use movement functions or convert to Cartesian.")
  def __mul__(self, scalar: float) -> 'Position':
      raise NotImplementedError("Scalar multiplication is not directly supported for PositionUTM.")
  def __rmul__(self, scalar: float) -> 'Position':
      raise NotImplementedError("Scalar multiplication is not directly supported for PositionUTM.")
  def __truediv__(self, scalar: float) -> 'Position':
      raise NotImplementedError("Scalar division is not directly supported for PositionUTM.")