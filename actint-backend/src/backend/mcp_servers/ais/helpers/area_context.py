import math
from typing import TypedDict
from backend.mcp_servers.ais.helpers.vessel_query import (
    get_all_latest_detections_helper,
    get_vessel_position_history_helper
)
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm, calculate_bearing
import math
from datetime import timedelta

"""
Description: 

This program predicts potential future intersections of vessels in a specified maritime area. 
It uses the latest AIS detections to calculate each vessel's speed and heading, then projects
their positions forward over the next 10 hours. Intersections are defined as instances where 
two vessels come within 3 nautical miles of each other within a 3-hour forecast window.

Key steps:
1. Fetch the latest AIS detections near a target latitude/longitude within a specified radius.
2. Filter detections to only include vessels with valid positions and recent timestamps.
3. Calculate each vessel’s current speed and direction based on its last two positions.
4. Project each vessel’s future trajectory, synchronizing to the most recent timestamp.
5. Detect intersections where two vessels are within 3 NM in the next 3 forecast hours.
6. Output a neatly formatted table of potential intersections including MMSI, approximate 
   position, and expected time.

Usage:
Set `lat` and `lon` for the area of interest (e.g., Port of Los Angeles) and `radius_nm` 
for the detection radius, then run the script.
"""


# Earth's radius in nautical miles
EARTH_RADIUS_NM = 3440.065


def calculate_future_position(lat: float, lon: float, speed_knots: float, bearing_deg: float, hours: float) -> tuple[float, float]:
    """Calculate future position given current position, speed, bearing, and time."""
    distance_nm = speed_knots * hours
    bearing_rad = math.radians(bearing_deg)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance_nm / EARTH_RADIUS_NM) +
                            math.cos(lat_rad) * math.sin(distance_nm / EARTH_RADIUS_NM) * math.cos(bearing_rad))
    
    new_lon_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(distance_nm / EARTH_RADIUS_NM) * math.cos(lat_rad),
                                       math.cos(distance_nm / EARTH_RADIUS_NM) - math.sin(lat_rad) * math.sin(new_lat_rad))

    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)


def get_future_intersections_in_area_helper(lat: str, lon: str, radius_nm: str) -> str:
    radius_nm = float(radius_nm)
    latest_detections = get_all_latest_detections_helper()

    #Only get the detections that are near the area of interest so we don't calculate if ships will intersect when they are on oppisite sides of the world. 
    # print([relevant['lon'] for relevant in latest_detections], flush=True)
    relevant_detections = [det for det in latest_detections if det['lat'] is not None and det['lon'] is not None and haversine_distance_nm(float(lat), float(lon), det['lat'], det['lon']) <= radius_nm * 2]
    latest_time = max(det['basedatetime'] for det in relevant_detections if det['basedatetime'] is not None)
    trajectories = []

    # For every relevant detection, get the last few positions and calculate the direction and speed, then use those to calculate several trajectory points for the next 10 hours from the most latest time. 
    for detection in relevant_detections:
        current_detection, previous_detection = get_vessel_position_history_helper(detection['mmsi'], limit=2)
        direction = calculate_bearing(previous_detection['lat'], previous_detection['lon'], current_detection['lat'], current_detection['lon'])
        distance = haversine_distance_nm(previous_detection['lat'], previous_detection['lon'], current_detection['lat'], current_detection['lon'])
        time_between = (current_detection['basedatetime'] - previous_detection['basedatetime']).total_seconds() / 3600
        knots = distance / time_between

                # Move vessel to latest_time first
        hours_since = (latest_time - current_detection["basedatetime"]).total_seconds() / 3600
        start_lat, start_lon = calculate_future_position(
            current_detection["lat"], current_detection["lon"], knots, direction, hours_since
        )


        trajectory = [
            calculate_future_position(start_lat, start_lon, knots, direction, hour)
            for hour in range(11)
        ]

        trajectories.append({
            "mmsi": detection["mmsi"],
            "points": trajectory
        })

    # After those are calculated, go through each ship and find if there are intersections with other ships inside of the desired area, then delete those ships. 
    intersections = []

    for i, ship1 in enumerate(trajectories):
        for ship2 in trajectories[i + 1:]:

            # only check first 3 forecast hours
            for hour in range(4):
                lat1, lon1 = ship1["points"][hour]
                lat2, lon2 = ship2["points"][hour]

                if haversine_distance_nm(lat1, lon1, lat2, lon2) <= 500:
                    intersection_data = (ship1["mmsi"], ship2["mmsi"], (lat1 + lat2)/2, (lon1 + lon2)/2, latest_time + timedelta(hours=hour))
                    intersections.append(intersection_data)
                    break

    return_string = """
Approximate Future Intersections in Area:\n
| Ship 1 MMSI | Ship 2 MMSI | Latitude | Longitude | Time        |
|-------------|-------------|----------|-----------|-------------|\n"""

    for mmsi1, mmsi2, lat, lon, time in intersections:
        return_string += f"| {mmsi1:11} | {mmsi2:11} | {lat:8.3f} | {lon:9.3f} | {time}\n"

    return_string += ("\n\nNote: Intersections are defined as vessels coming within 15 NM of each other within the next 3 forecast hours, ships may come close to each other, but this may not be reported as an intersection.")
    return return_string



if __name__ == "__main__":
    # Downtown Los Angeles
    lat = 34.0522
    lon = -118.2437

    # radius in nautical miles (adjust as needed)
    radius_nm = 50

    result = get_future_intersections_in_area_helper(lat, lon, radius_nm)
    print(result)