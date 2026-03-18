from abc import ABC
from .Position import Position, PositionLatLon, PositionUTM, Position3D

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
                 speed: float,
                 error: float,
                 ):
        """
        Initialize a Destination instance.
        
        Args:
            position (Position): The geometric position of the destination
            speed (float): Target speed to reach the next destination
            error (float): Acceptable error margin for determining if destination is reached
        """
        self.position = position
        self._target_speed_to_next_destination = speed
        self.error = error
        self.heading_error: float = 0.174533 # ~10 degrees in radians
    @property
    def target_speed_to_next_destination(self) -> float:
        speed = self._target_speed_to_next_destination
        return speed
    
    def has_reached(self, position: Position,) -> bool:
        """
        Check if a given position has reached this destination within the error margin.
        
        Args:
            position (Position): The position to check
            
        Returns:
            bool: True if the position is within the error margin of the destination,
                  False otherwise
        """
        distance_to_dest = self.position.distance_to(position)
        position_error = abs(distance_to_dest) < self.error

        return position_error

class Destination2D(Destination):
    """
    2D destination class inheriting from Destination.
    
    This class represents a destination point in 2-dimensional space.
    It inherits all functionality from the base Destination class but is
    specifically designed for 2D positions.
    
    Attributes:
        position (PositionLatLon): The 2D geometric position of the destination
        target_speed_to_next_destination (float): Target speed to reach the next destination
        error (float): Acceptable error margin for determining if destination is reached
    """
    
    def __init__(self,
                 position: PositionLatLon,
                 target_speed_to_next_destination: float,
                 error: float,
                 ):
        """
        Initialize a 2D Destination instance.
        
        Args:
            position (PositionLatLon): The 2D geometric position of the destination
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
            target_speed_to_next_destination (float): Target speed to reach the next destination
            error (float): Acceptable error margin for determining if destination is reached
        """
        super().__init__(position, target_speed_to_next_destination, error)