import numpy as np
from numpy.typing import NDArray


class Vector2D:
  def __init__(self, x: float, y: float) -> None:
    self._vector = np.array([x, y], dtype=np.float64)

  @property
  def vector(self) -> NDArray[np.float64]:
    return self._vector.copy()
  
  @property
  def x(self) -> float:
    return self._vector[0]
  
  @x.setter
  def x(self, value: float) -> None:
    self._vector[0] = value

  @property
  def y(self) -> float:
    return self._vector[1]

  @y.setter
  def y(self, value: float) -> None:
    self._vector[1] = value

  def __str__(self):
    return f'{type(self).__name__}(x={self.x:.2f}, y={self.y:.2f})'
  
  def __repr__(self):
    return f'{type(self).__name__}(x={self.x}, y={self.y})'
  
  def __eq__(self, other):
    if not isinstance(other, Vector2D):
      return False
    return np.array_equal(self._vector, other.vector)
  
  def __add__(self, other):
    if isinstance(other, Vector2D):
      return Vector2D(self.x + other.x, self.y + other.y)
    raise TypeError(f"Can only add Vector2D to Vector2D NOT {type(other).__name__}")
  
  def __sub__(self, other):
    if isinstance(other, Vector2D):
      return Vector2D(self.x - other.x, self.y - other.y)
    raise TypeError(f"Can only subtract Vector2D from Vector2D NOT {type(other).__name__}")

  def truncate(v: 'Vector2D', limit: float) -> 'Vector2D':
    """
    Docstring for truncate
    """
    vec = v.vector
    norm = np.linalg.norm(vec)
    if norm > limit:
        scaled = vec * (limit / norm)
        return Vector2D(*[float(x) for x in scaled])
    return v


class Vector3D:
  def __init__(self, x: float, y: float, z: float) -> None:
    self._vector = np.array([x, y, z], dtype=np.float64)

  @property
  def vector(self) -> NDArray[np.float64]:
    return self._vector.copy()
  
  @property
  def x(self) -> float:
    return self._vector[0]
  
  @x.setter
  def x(self, value: float) -> None:
    self._vector[0] = value

  @property
  def y(self) -> float:
    return self._vector[1]
  
  @y.setter
  def y(self, value: float) -> None:
    self._vector[1] = value

  @property
  def z(self) -> float:
    return self._vector[2]
  
  @z.setter
  def z(self, value: float) -> None:
    self._vector[2] = value

  def __str__(self):
    return f'{type(self).__name__}(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f})'
  
  def __repr__(self):
    return f'{type(self).__name__}(x={self.x}, y={self.y}, z={self.z})'
  
  def __eq__(self, other):
    if not isinstance(other, Vector3D):
      return False
    return np.array_equal(self._vector, other.vector)
  
  def __add__(self, other):
    if isinstance(other, Vector3D):
      return Vector3D(self.x + other.x, self.y + other.y, self.z + other.z)
    raise TypeError(f"Can only add Vector3D to Vector3D NOT {type(other).__name__}")
  
  def __sub__(self, other):
    if isinstance(other, Vector3D):
      return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)
    raise TypeError(f"Can only subtract Vector3D from Vector3D NOT {type(other).__name__}")










    