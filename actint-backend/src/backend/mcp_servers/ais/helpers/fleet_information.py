from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_latest_location_helper, query_static_data_helper, get_static_data_helper

from datetime import timedelta
import statistics


DISTANCE_THRESHOLD = 10.0
TIME_LAST_SEEN_THRESHOLD = timedelta(hours=2)


def get_fleet_names():
    all_vessels = get_static_data_helper()
    fleet_names = set(vessel['fleet'] for vessel in all_vessels if vessel['fleet'] is not None and vessel['fleet'] != '' and vessel['fleet'] != 'Unknown')
    return list(fleet_names)


def get_fleet_position_helper(canonical_name):
    """Calculates the average position of a fleet. (uses this as the fleet position)"""

    vessels_in_fleet = query_static_data_helper({"fleet": canonical_name})
    
    if not vessels_in_fleet:
        return f"No Vessels in fleet {canonical_name}"
    
    # Get latest positions: assuming format [mmsi, timestamp_ms, lat, lon]
    vessels_most_recent_positions = []
    for vessel in vessels_in_fleet:
        position = get_vessel_latest_location_helper(vessel['mmsi'])  # [mmsi, ts_ms, lat, lon]
        if position:
            vessels_most_recent_positions.append(position)
    
    if not vessels_most_recent_positions:
        return f"No recent positions found for fleet {canonical_name}"

    # Sort by timestamp (most recent first)
    vessels_most_recent_positions_sorted = sorted(
        vessels_most_recent_positions,
        key=lambda x: x['basedatetime'],
        reverse=True
    )
    
    most_recent_timestamp = vessels_most_recent_positions_sorted[0]['basedatetime']
    vessels_within_time_threshold = [
        pos for pos in vessels_most_recent_positions_sorted
        if pos['basedatetime'] >= (most_recent_timestamp - TIME_LAST_SEEN_THRESHOLD)
    ]
    
    if not vessels_within_time_threshold:
        return f"No vessels within time threshold for fleet {canonical_name}"
    
    # Extract lat/lon for median calculation
    latitudes = [pos['lat'] for pos in vessels_within_time_threshold] 
    longitudes = [pos['lon'] for pos in vessels_within_time_threshold]
    
    median_lat = statistics.median(latitudes)
    median_lon = statistics.median(longitudes)
    
    # Filter for distance threshold from median
    filtered_positions = [
        pos for pos in vessels_within_time_threshold
        if abs(pos['lat'] - median_lat) <= DISTANCE_THRESHOLD and abs(pos['lon'] - median_lon) <= DISTANCE_THRESHOLD
    ]
    
    if not filtered_positions:
        return f"No vessels within distance threshold for fleet {canonical_name}"
    
    # Calculate average
    ave_lat = sum(pos['lat'] for pos in filtered_positions) / len(filtered_positions)
    ave_lon = sum(pos['lon'] for pos in filtered_positions) / len(filtered_positions)
    
    # print(ave_lat, ave_lon)
    return (ave_lat, ave_lon)



def ship_near_fleet_helper(mmsi):
    vessel_info = get_static_data_helper(mmsi)
    fleet = vessel_info['fleet']
    if not fleet:
        return f"Vessel with MMSI {mmsi} is not assigned to a fleet."
    fleetLat, fleetLon = get_fleet_position_helper(fleet)
    most_rescent_position = get_vessel_latest_location_helper(mmsi)
    if haversine_distance_nm(most_rescent_position['lat'], most_rescent_position['lon'], fleetLat, fleetLon) <= DISTANCE_THRESHOLD:
        return f"This ship is considered to be in the fleet becuase it is within {DISTANCE_THRESHOLD} NM of the fleet position."
    else: 
        return f"This ship is not coonsidered to be in the fleet becuaase it is more than {DISTANCE_THRESHOLD} NM from the fleet position."


def fleets_information_helper():
    fleet_names = get_fleet_names()
    fleet_positions = {}
    for fleet in fleet_names:
        position = get_fleet_position_helper(fleet)
        fleet_positions[fleet] = position

    result = f"List of the fleet names and their positions\n\n"
    for fleet, position in fleet_positions.items():
        result += f"Fleet name: {fleet}, Position: {position}\n"
    return fleet_positions