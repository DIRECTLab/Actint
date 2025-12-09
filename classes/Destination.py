from abc import ABC
from Position import Position, Position2D, Position3D

class Destination(ABC):
    """
    Abstract base class representing a destination point in space.
    
    This class serves as a foundation for different types of destinations
    (e.g. 2D and 3D) and provides common functionality for distance calculations
    and destination reach detection.
    
    Attributes:
        position (Position): The position of the destination
        target_speed_to_next_destination (float): Target speed to reach the next destination
        error (float): Acceptable error margin for determining if destination is reached
    """
    
    def __init__(self,
                 position: Position,
                 target_speed_to_next_destination: float,
                 error: float,
                 ):
        """
        Initialize a Destination instance.
        
        Args:
            position (Position): The geometric position of the destination
            target_speed_to_next_destination (float): Target speed to reach the next destination
            error (float): Acceptable error margin for determining if destination is reached
        """
        self.position = position
        self.target_speed_to_next_destination = target_speed_to_next_destination
        self.error = error
        self.heading_error: float = 0.174533 # ~10 degrees in radians
    
    def distance_to_dest(self, position: Position) -> float:
        """
        Calculate the distance from a given position to this destination.
        
        Args:
            position (Position): The position to calculate distance from
            
        Returns:
            float: The distance between the given position and this destination
        """
        return self.position.distance_to(position)
    
    def has_reached(self, position: Position, heading: float) -> bool:
        """
        Check if a given position has reached this destination within the error margin.
        
        Args:
            position (Position): The position to check
            
        Returns:
            bool: True if the position is within the error margin of the destination,
                  False otherwise
        """
        heading_error = abs(heading - self.position.get_heading(position)) < self.heading_error

        distance_to_dest = self.distance_to_dest(position)
        position_error = abs(distance_to_dest) < self.error

        return position_error and heading_error

class Destination2D(Destination):
    """
    2D destination class inheriting from Destination.
    
    This class represents a destination point in 2-dimensional space.
    It inherits all functionality from the base Destination class but is
    specifically designed for 2D positions.
    
    Attributes:
        position (Position2D): The 2D geometric position of the destination
        target_speed_to_next_destination (float): Target speed to reach the next destination
        error (float): Acceptable error margin for determining if destination is reached
    """
    
    def __init__(self,
                 position: Position2D,
                 target_speed_to_next_destination: float,
                 error: float,
                 ):
        """
        Initialize a 2D Destination instance.
        
        Args:
            position (Position2D): The 2D geometric position of the destination
            target_speed_to_next_destination (float): Target speed to reach the next destination
            error (float): Acceptable error margin for determining if destination is reached
        """
        super().__init__(position, target_speed_to_next_destination, error)

class Destination3D(Destination):
    """
    3D destination class inheriting from Destination.
    
    This class represents a destination point in 3-dimensional space.
    It inherits all functionality from the base Destination class but is
    specifically designed for 3D positions.
    
    Attributes:
        position (Position3D): The 3D geometric position of the destination
        target_speed_to_next_destination (float): Target speed to reach the next destination
        error (float): Acceptable error margin for determining if destination is reached
    """
    
    def __init__(self,
                 position: Position3D,
                 target_speed_to_next_destination: float,
                 error: float,
                 ):
        """
        Initialize a 3D Destination instance.
        
        Args:
            position (Position3D): The 3D geometric position of the destination
            target_speed_to_next_destination (int): Target speed to reach the next destination
            error (float): Acceptable error margin for determining if destination is reached
        """
        super().__init__(position, target_speed_to_next_destination, error)