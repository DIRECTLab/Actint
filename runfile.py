import csv
import queue

from numpy import rint
from classes import Vehicle2D, Vehicle3D, Position, Position2D, Position3D
from classes.Destination import Destination2D, Destination3D


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def read_csv(filepath: str) -> list:
    """
    Read simulation data from a CSV file and return a list of vehicles.

    Segregated parsing:
    - Destinations section: builds per-vehicle destination queues
    - Vehicles section: constructs vehicles and attaches their destination queues

    Returns:
        list: vehicles (each vehicle has its destination_queue attached)
    """

    with open(filepath, "r", newline="") as csvfile:
        rows = list(csv.DictReader(csvfile))

    # Destinations section
    dest_queues_by_id: dict[int, queue.Queue] = {}
    for row in rows:
        if not _parse_bool(row.get("is_destination", "false")):
            continue
        vehicle_id = int(row["vehicle_id"])  # required
        dq = dest_queues_by_id.setdefault(vehicle_id, queue.Queue())

        dest_x = float(row["position_x"])  # required
        dest_y = float(row["position_y"])  # required
        dest_speed = float(row.get("dest_speed", 50.0))
        dest_error = float(row.get("dest_error", 5.0))
        is_3d = _parse_bool(row.get("is_3d", "false"))

        if is_3d:
            dest_z = float(row.get("position_z", 0.0))
            dest_pos = Position3D(dest_x, dest_y, dest_z)
            dest = Destination3D(dest_pos, dest_speed, dest_error)
        else:
            dest_pos = Position2D(dest_x, dest_y)
            dest = Destination2D(dest_pos, dest_speed, dest_error)

        dq.put(dest)

    # Vehicles section
    vehicles: list = []
    for row in rows:
        if row.get("is_destination", "true").strip().lower() == "true":
            continue
        vehicle_id = int(row["vehicle_id"])  # required
        vehicle_type = row["vehicle_type"]
        is_3d = _parse_bool(row.get("is_3d", "false"))
        action = row.get("action", "none")
        dq = dest_queues_by_id.get(vehicle_id, queue.Queue())

        if is_3d:
            pos_x = float(row["position_x"])  # required
            pos_y = float(row["position_y"])  # required
            pos_z = float(row.get("position_z", 0.0))
            position = Position3D(pos_x, pos_y, pos_z)

            vehicle = Vehicle3D(
                max_altitude=int(row.get("max_altitude", 1000)),
                action=action,

                position=position,
                max_speed=float(row.get("max_speed", 100.0)),
                max_force=float(row.get("max_force", 200.0)),
                max_turn_rate=float(row.get("max_turn_rate", 3.14159)),
                vehicle_type=vehicle_type,
                vehicle_id=vehicle_id,
                destination_queue=dq,
                time_step=float(row.get("time_step", 1)),
            )
        else:
            pos_x = float(row["position_x"])  # required
            pos_y = float(row["position_y"])  # required
            position = Position2D(pos_x, pos_y)

            vehicle = Vehicle2D(
                position=position,
                vehicle_type=vehicle_type,
                vehicle_id=vehicle_id,
                destination_queue=dq,
                time_step=float(row.get("time_step", 1)),
                velocity_x=float(row.get("velocity_x", 0.0)),
                velocity_y=float(row.get("velocity_y", 0.0)),
                mass=float(row.get("mass", 1.0)),
                max_speed=float(row.get("max_speed", 100.0)),
                max_force=float(row.get("max_force", 200.0)),
                scale=float(row.get("scale", 10.0)),
                max_turn_rate=float(row.get("max_turn_rate", 3.14159)),
                action=action,
            )

        vehicles.append(vehicle)

    return vehicles


if __name__ == "__main__":
    vehicles = read_csv("simulation_data.csv")
    print(f"Loaded {len(vehicles)} vehicles")
    for v in vehicles:
        for i in range(150):
            if i % 5 == 0:
                print(f"Vehicle {v.vehicle_id}: {v.vehicle_type} at {v.position} with destination: {v.next_destination.position if v.next_destination else 'None'}")
            v.update(1, 10000, 10000)
        print(f"Vehicle {v.vehicle_id}'s action: {v.action}")

