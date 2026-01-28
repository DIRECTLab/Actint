import json
import queue
from classes import Vehicle2D, Vehicle3D, Position, Position2D, Position3D
from classes import Destination2D, Destination3D
from classes import Settings

def read_json(filename: str) -> tuple[list[Vehicle2D | Vehicle3D], Settings]:
    vehicles: list[Vehicle2D | Vehicle3D] = []
    with open(filename, 'r') as f:
        data = json.load(f)


        settings: Settings = Settings(
        time_step=data['sim_settings']['time_step'],
        latlon_origin=data['sim_settings']['latlon_origin'],
        output_file_2d=data['sim_settings']['output_file_2d'],
        output_file_3d=data['sim_settings']['output_file_3d'],
        start_time=data['sim_settings']['start_time']
    )
        for v in data['vehicles']:
            id = v['id']
            type = v['type']
            is_3d = v['is_3d']
            max_speed = v['properties']['max_speed']
            max_force = v['properties']['max_force']
            destinations = queue.Queue()
            if is_3d:
                settings.has_vehicle3d = True
                for d in v['destinations']:
                    position = Position3D(float(d['position']['x']), float(d['position']['y']), float(d['position']['z']))
                    action = d['action']
                    error = d['error']
                    speed = d['speed']
                    destinations.put(Destination3D(position, speed, error, action))
                max_altitude = v['properties']['max_altitude']
                
                position = Position3D(float(v['properties']['position']['x']), float(v['properties']['position']['y']), float(v['properties']['position']['z']))
                vehicle = Vehicle3D(
                    vehicle_id=id,
                    vehicle_type=type,
                    destination_queue=destinations,
                    time_step=settings.time_step,
                    position=position,
                    max_speed=max_speed,
                    max_force=max_force,
                    max_altitude=max_altitude,
                    )
                vehicles.append(vehicle)
            else:
                settings.has_vehicle2d = True
                for d in v['destinations']:
                    position = Position2D(float(d['position']['x']), float(d['position']['y']))
                    action = d['action']
                    error = d['error']
                    speed = d['speed']
                    destinations.put(Destination2D(position, speed, error, action))
                
                position = Position2D(float(v['properties']['position']['x']), float(v['properties']['position']['y']))
                vehicle = Vehicle2D(
                    vehicle_id=id,
                    vehicle_type=type,
                    destination_queue=destinations,
                    time_step=settings.time_step,
                    position=position,
                    max_speed=max_speed,
                    max_force=max_force,
                    )
                vehicles.append(vehicle)
    return vehicles, settings

if __name__ == "__main__":
    vehicles, settings = read_json("example_ground_truth_runfile.json")
    print(f"Loaded {len(vehicles)} vehicles")
    for v in vehicles:
        for i in range(200):
            if not v.done:
                print(f"Vehicle {v.vehicle_id}: {v.vehicle_type} at {v.position} with destination: {v.next_destination.position if v.next_destination else 'None'} and action: {v.next_destination.action if v.next_destination else 'None'}")
            v.update(settings.time_step)


