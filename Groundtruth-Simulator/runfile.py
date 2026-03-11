import json
import queue
from classes import Vehicle2D, Vehicle3D
from classes import Destination2D, Destination3D
from classes import Settings
from classes import PositionLatLon


def read_json(filename: str) -> tuple[list[Vehicle2D | Vehicle3D], Settings]:
    vehicles: list[Vehicle2D | Vehicle3D] = []
    with open(filename, 'r') as f:
        data = json.load(f)


        settings: Settings = Settings(
        time_step=data['sim_settings'].get('time_step', .7),
        latlon_origin=data['sim_settings'].get('latlon_origin', None),
        output_file_2d=data['sim_settings'].get('output_file_2d', 'JFN-Simulator_output_2d'),
        output_file_3d=data['sim_settings'].get('output_file_3d', 'JFN-Simulator_output_3d'),
        start_time=data['sim_settings'].get('start_time', '2026-01-29 17:45:00'),
        print_format=data['sim_settings'].get('print_format', 'json'),
        print_time_as=data['sim_settings'].get('print_time_as', 'iso'),
        time_format=data['sim_settings'].get('time_format', "%Y-%m-%d %H:%M:%S")
    )
        for v in data['vehicles']:
            id = v['vehicle_id']
            type = v.get('type', 'default')
            is_3d = v.get('is_3d', False)
            max_speed = v['properties'].get('max_speed', 100.0)
            max_force = v['properties'].get('max_force', 200.0)
            action = v.get('action', 'seek').lower()
            target_vehicle = v.get('target_id', None)
            follow_distance = v.get('follow_distance', 0.0)
            stay_time = v.get('stay_time', 50.0)


            destinations = queue.Queue()
            if is_3d:
                settings.has_vehicle3d = True
                for d in v.get('destinations', []):
                    error = d.get('error', 5.0)
                    speed = d.get('speed', 50.0)
                    destinations.put(Destination3D(PositionLatLon(d['position'].get('lat', 100), (d['position'].get('lon', 100)+180)%360-180), speed, error))
                max_altitude = v['properties'].get('max_altitude', 1200)
                
                vehicle = Vehicle3D(
                    initial_global_latitude=float(v['properties']['position'].get('lat', 0)),
                    initial_global_longitude=float(v['properties']['position'].get('lon', 0)),
                    initial_global_altitude=float(v['properties']['position'].get('z', 0)),
                    vehicle_id=id,
                    vehicle_type=type,
                    destination_queue=destinations,
                    time_step=settings.time_step,
                    max_speed=max_speed,
                    max_force=max_force,
                    max_altitude=max_altitude,
                    action=action,
                    target_id=target_vehicle,
                    follow_distance=follow_distance,
                    stay_time=stay_time,
                    )
                print(f"Created 3D Vehicle {vehicle}")
                vehicles.append(vehicle)
            else:
                settings.has_vehicle2d = True
                for d in v.get('destinations', []):
                    error = d.get('error', 30.0)
                    speed = d.get('speed', 50.0)
                    destinations.put(Destination2D(PositionLatLon(d['position'].get('lat', 100), (d['position'].get('lon', 100)+180)%360-180), speed, error))
                
                
                vehicle = Vehicle2D(
                    initial_global_latitude=float(v['properties']['position'].get('lat', 0)),
                    initial_global_longitude=float(v['properties']['position'].get('lon', 0)),
                    vehicle_id=id,
                    vehicle_type=type,
                    destination_queue=destinations,
                    time_step=settings.time_step,
                    max_speed=max_speed,
                    max_force=max_force,
                    action=action,
                    target_id=target_vehicle,
                    follow_distance=follow_distance,
                    stay_time=stay_time,
                    )
                vehicles.append(vehicle)
    return vehicles, settings

if __name__ == "__main__":
    vehicles, settings = read_json("example_ground_truth_runfile.json")
    print(f"Loaded {len(vehicles)} vehicles")
    for v in vehicles:
        for i in range(200):
            if not v.done:
                print(f"Vehicle {v.vehicle_id}: {v.vehicle_type} at {v.position_utm}{v.position_latlon} with destination: {v.next_destination.position if v.next_destination else 'None'} and action: {v.action if v.next_destination else 'None'}")
            v.update(settings.time_step)
