from Position import Position, Position2D, Position3D

class Destination:
    def __init__(self,
                 position: Position,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
          self.position = position
          self.target_speed_to_next_destination = target_speed_to_next_destination
          self.error = error

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