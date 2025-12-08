from abc import abstractmethod
import numpy as np

class Position():
  @abstractmethod
  def distance_to(self, position: 'Position') -> float:
    pass

class Position2D(Position):
  def __init__(
      self,
      x: float,
      y: float
  ):
    self.x = x
    self.y = y

  def distance_to(self, position):
    # If the other position is also a Position2D, ignore z components
    return np.sqrt(np.dot(self.x - position.x, self.y - position.y))


class Position3D(Position2D):
  def __init__(self, x: float, y: float, z: float):
    super().__init__(x, y)
    self.position_z = z

  def distance_to(self, position):
    # If the other position is a Position2D, ignore z components
    if isinstance(position, Position2D):
        return super().distance_to(position)
    else:
        return np.linalg.norm([self.x, self.y, self.z] - [position.x, position.y, position.z])