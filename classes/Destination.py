from Position import Position2D, Position3D

class Destination2D:
    def __init__(self,
                 position: Position2D,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
        self.position = position
        self.target_speed_to_next_destination = target_speed_to_next_destination
        self.error = error

class Destination3D(Destination2D):
    def __init__(self,
                 position: Position3D,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
        self.position = position
        self.target_speed_to_next_destination = target_speed_to_next_destination
        self.error = error