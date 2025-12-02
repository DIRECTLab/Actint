class Destination:
    def __init__(self,
                 position_x: float,
                 position_y: float,
                 target_speed_to_next_destination: int,
                 error: float,
                 ):
        self.position_x = position_x
        self.position_y = position_y
        self.target_speed_to_next_destination = target_speed_to_next_destination
        self.error = error