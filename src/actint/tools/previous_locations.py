from actint.data_processing.query_database import query_ais_positions, query_vessels, query_fleets
from dataclasses import dataclass
from actint.data_processing.rag import VesselPosition
from actint.tools.utils.distance_calculation import haversine_distance_nm

from datetime import datetime, timedelta


def get_vehicle_locations(mmsi: int) -> list[VesselPosition]:
    """Get all recorded positions for a vessel."""
    data = query_ais_positions({"mmsi": mmsi})

    positions = []
    for row in data:
        position = VesselPosition(
            mmsi=row[1],
            vessel_name=row[8],
            timestamp=row[2],
            lat=row[3],
            lon=row[4],
            sog=row[5],
            cog=row[6],
            heading=row[7],
        )
        positions.append(position)
        positions.sort(key=lambda x: x.timestamp, reverse=True)
    
    return positions


def ship_following(mmsi1, mmsi2):
    """Determine if two vessels have been following each other."""
    
    mmsi1_name = query_vessels({"mmsi": mmsi1})[0][1]
    mmsi2_name = query_vessels({"mmsi": mmsi2})[0][1]
    THRESHOLD_TIME = timedelta(hours = 1)
    THRESHOLD_DISTANCE = 5.0 #Latitude/longitude degrees for now

    positions1 = get_vehicle_locations(mmsi1)
    positions2 = get_vehicle_locations(mmsi2)

    in_previous_area = []
    
    for position1 in positions1:
        follows_past_hour = []
        for position2 in positions2:
            if datetime.strptime(position1.timestamp, "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(position2.timestamp, "%Y-%m-%dT%H:%M:%S.%f") <= THRESHOLD_TIME: 
                follows_past_hour.append(position2)
        
        for follows in follows_past_hour:
            distance = haversine_distance_nm(position1.lat, position1.lon, follows.lat, follows.lon)
            if distance <= THRESHOLD_DISTANCE: 
                in_previous_area.append(True)
                break                                    #make sure this does the right thing to go to the next for loop, might be break
        
        in_previous_area.append(False)
                

        
    
    string = f"Vessel {mmsi2_name} went to the same area as {mmsi1_name} within {THRESHOLD_TIME} of when {mmsi1_name} was there {sum(in_previous_area)}/{len(in_previous_area)} times."
    return string