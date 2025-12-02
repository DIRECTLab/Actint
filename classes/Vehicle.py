from queue import Queue

class Vehicle:

    def __init__(self,
                 vehicle_type: str,
                 vehicle_id: int,
                 destination_queue: Queue,
                 time_step: int,
                 ):
        self.vehicle_type = vehicle_type
        self.vehicle_id = vehicle_id
        self.time_step = time_step
        self.destination_queue = destination_queue
        self.next_desitnation = None
            
        