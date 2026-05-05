from backend.data_processing.query_database import query_ais_positions, query_vessels, query_fleets
from backend.mcp_servers.ais.helpers.previous_locations import get_vehicle_locations
from dataclasses import dataclass
from datetime import datetime, timedelta
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
import statistics

DISTANCE_THRESHOLD = 10.0
TIME_LAST_SEEN_THRESHOLD = timedelta(hours = 2)


def calculate_fleet_position(canonical_name):
    """Calculate the average position of a fleet."""



    vessels_in_fleet = query_vessels({"fleet": canonical_name})
    if not vessels_in_fleet:
        raise ValueError(f"No Vessels in fleet {canonical_name}")
    
     
    latitudes = []
    longitudes = []

    """
    If ships are not seen within TIME_LAST_SEEN_THRESHOLD of the most recently seen ship, 
    they are not counted to calculate the position of the fleet.
    """


    sorted_vessels = sorted(
        vessels_in_fleet,
        key=lambda x: datetime.strptime(x[14], "%Y-%m-%dT%H:%M:%S.%f"),
        reverse=True
    )

    most_recently_seen_vessel_time = datetime.strptime(
        sorted_vessels[0][14], "%Y-%m-%dT%H:%M:%S.%f"
    )

    vessels_within_time_threshold = []


    for vessel in vessels_in_fleet:
        if datetime.strptime(vessel[14], "%Y-%m-%dT%H:%M:%S.%f") + TIME_LAST_SEEN_THRESHOLD < most_recently_seen_vessel_time:
            vessels_within_time_threshold.append(vessel)

    vessels_positions = []
    for vessel in vessels_within_time_threshold:
        positions = get_vehicle_locations(vessel[0])
        vessels_positions.append(positions[0])
        

    print(vessels_positions)
    

    median_lat = statistics.median(v.lat for v in vessels_positions)
    median_lon = statistics.median(v.lon for v in vessels_positions)
    

    for vesselPosition in vessels_positions:
        if(abs(vesselPosition.lat) - abs(median_lat) <= DISTANCE_THRESHOLD and abs(vesselPosition.lon) - abs(median_lon) <= DISTANCE_THRESHOLD):
            latitudes.append(vesselPosition.lat)
            longitudes.append(vesselPosition.lon)
    
    ave_lat = sum(latitudes) / len(latitudes)
    ave_lon = sum(longitudes) / len(longitudes)

    return ave_lat, ave_lon






def is_ship_in_fleet(mmsi):
    
    fleet = query_vessels({"mmsi": mmsi})[0][11]
    fleetLat, fleetLon = calculate_fleet_position(fleet)
    ship_locations = get_vehicle_locations(mmsi)
    sorted_locations = sorted(ship_locations, key=lambda x: x.timestamp, reverse=True)
    most_rescent_AIS = sorted_locations[0]

    if haversine_distance_nm(most_rescent_AIS.lat, most_rescent_AIS.lon, fleetLat, fleetLon) <= DISTANCE_THRESHOLD:
        return f"This ship is in the fleet (Within {DISTANCE_THRESHOLD} NM of the fleet)"
    else: 
        return f"This ship is not in the fleet (More than {DISTANCE_THRESHOLD} NM from the fleet)"



