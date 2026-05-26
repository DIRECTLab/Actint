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
        raise ValueError(f"No vessels in fleet {canonical_name}")
    
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
    
    return (ave_lat, ave_lon)




def get_vessels_in_fleet_helper(canonical_name: str):
    vessels_in_fleet = query_static_data_helper({"fleet": canonical_name})
    if not vessels_in_fleet:
        raise ValueError("No ships in fleet")
    result = f"\nFleet {canonical_name} has vessels with MMSIs:\n\n"
    for vessel in vessels_in_fleet:
        result += f" - {vessel['mmsi']}\n"
    return result


def get_fleets_information_helper():
    fleet_names = get_fleet_names()
    fleet_positions = {}
    for fleet in fleet_names:
        position = get_fleet_position_helper(fleet)
        fleet_positions[fleet] = position

    result = f"\nList of the fleet names and their positions:\n\n"
    for fleet, position in fleet_positions.items():
        result += (
            f"Fleet: {fleet}\n"
            f" - Position: {position}\n"
            )
    return result
