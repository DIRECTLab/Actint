from abc import ABC
from Position import Position, Position2D, Position3D

class Destination(ABC):
    def __init__(self,
                 position: Position,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
          self.position = position
          self.target_speed_to_next_destination = target_speed_to_next_destination
          self.error = error

    def distance_to_dest(self, position: Position) -> float:
      return self.position.distance_to(position)

    def has_reached(self, position: Position) -> bool:
      distance_to_dest = self.distance_to_dest(position)
      return abs(distance_to_dest) < self.error

class Destination2D(Destination):
    def __init__(self,
                 position: Position2D,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
        super().__init__(position, target_speed_to_next_destination, error)
        

class Destination3D(Destination):
    def __init__(self,
                 position: Position3D,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
        super().__init__(position, target_speed_to_next_destination, error)