import queue
from classes import Destination

class Vehicle:
    def __init__(self,
                 vehicle_type: str,
                 vehicle_id: int,
                 destination_queue: queue.Queue,
                 time_step: int,
                 ):
        self.vehicle_type = vehicle_type
        self.vehicle_id = vehicle_id
        self.time_step = time_step
        self.destination_queue = destination_queue
        self.next_destination: Destination = None

    def update(self):
        raise NotImplementedError("This method should be overridden by subclasses")
    
    def _assign_next_destination(self) -> bool:
        """Assign the next destination from the queue to `self.next_destination`.

        Returns True if a destination was assigned, otherwise False.
        """
        try:
            self.next_destination = self.destination_queue.get_nowait()
            return True
        except queue.Empty:
            self.next_destination = None
            return False
        
    def _has_next_destination(self) -> bool:
        """Check if there is a next destination in the queue.

        Returns True if there is at least one destination in the queue, otherwise False.
        """
        return not self.destination_queue.empty()