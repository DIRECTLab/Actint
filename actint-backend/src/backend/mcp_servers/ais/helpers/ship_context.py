"""
Latitude/Longitude Context Tool for LLM.

Provides geographic context for coordinates including:
- Reverse geocoding (location names)
- Maritime region identification
- Distance to notable locations (ports, coastlines)
- Bearing and direction calculations
"""
from typing import Optional, Tuple
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
from backend.mcp_servers.utils.important_locations import MARITIME_REGIONS, MAJOR_PORTS, STRATEGIC_WATERWAYS, CONTINENTS
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_latest_location_helper, get_all_mmsis, get_all_latest_detections_helper, get_vessel_latest_location_helper
from backend.mcp_servers.ais.helpers.vessel_query import query_static_data_helper, get_vessel_latest_location_helper, get_vessel_position_history_helper
# We may want to have a reverse georder eventually

def get_vessel_general_information_helper(mmsi: str):
    mmsi = int(mmsi)
    vessel_info = query_static_data_helper({"mmsi": mmsi})
    if vessel_info:
        vessel_info = vessel_info[0]
    else:
        raise ValueError(f"No vessel found with MMSI {mmsi}")
    latest_location_info = get_vessel_latest_location_helper(mmsi)

    return_string = f"""
Ship Information for MMSI {mmsi}:
Name: {vessel_info['vesselname']}
Home Base: {vessel_info['homebase']}
Parent Command: {vessel_info['parentcommand']}
Fleet: {vessel_info['fleet']}
Last Detction:
    Timestamp: {latest_location_info['basedatetime']}
    Lat: {latest_location_info['lat']}, Lon: {latest_location_info['lon']}
    Speed Over Ground: {latest_location_info['sog']} knots
    Course Over Ground: {latest_location_info['cog']} degrees
    Heading: {latest_location_info['heading']} degrees
"""
    return return_string


def get_vessel_locations_helper(mmsi: str, page: str = '1') -> str:
    PAGE_SIZE = 8
    mmsi = int(mmsi)
    page = int(page)
    if mmsi not in get_all_mmsis():
        raise ValueError("No valid mmsis")
    positions = get_vessel_position_history_helper(mmsi)
    start_index = (page - 1) * PAGE_SIZE
    end_index = ((page) * PAGE_SIZE) - 1
    indexed_positions = positions[start_index:end_index]

    positions_prompt = (
        "Idx | Latitude  | Longitude   | SOG (kt) | COG (deg) | Time\n"
        "----+-----------+-------------+----------+-----------+----------\n"
    )

    for i, position in enumerate(indexed_positions, start=start_index + 1):
        time_str = position["basedatetime"].strftime("%H:%M:%S")

        positions_prompt += (
            f"{i:>3} | "
            f"{position['lat']:>9.5f} | "
            f"{position['lon']:>11.5f} | "
            f"{position['sog']:>8.1f} | "
            f"{position['cog']:>9.1f} | "
            f"{time_str}\n"
        )

        prompt = (
            f"Vessel positions ({start_index + 1}-{end_index + 1})\n\n"
            f"{positions_prompt}\n"
            f"If you need to retrieve the next 8 positions, use:\n"
            f"get_vessel_locations(mmsi=\"{mmsi}\", page=\"{page + 1})\""
        )

    return prompt


def get_vessels_last_seen_helper():
    detections = get_all_latest_detections_helper()
    prompt = (
        "MMSI       | Latitude | Longitude | SOG | COG  | Time \n"
        "-----------+----------+-----------+-----+------+----------\n"
    )

    for detection in detections:
        time_str = detection['basedatetime'].strftime("%H:%M:%S") \
            if hasattr(detection["basedatetime"], "strftime") \
            else str(detection["basedatetime"])
        
        lat_str = f"{detection['lat']:7.2f}" if detection['lat'] is not None else " None  "
        lon_str = f"{detection['lon']:7.2f}" if detection['lon'] is not None else " None  "
        sog_str = f"{detection['sog']:4.1f}" if detection['sog'] is not None else "None"
        cog_str = f"{detection['cog']:5.1f}" if detection['cog'] is not None else "None "
        prompt += (
            f"{detection['mmsi']:<10} | "
            f"{lat_str} | "
            f"{lon_str} | "
            f"{sog_str} | "
            f"{cog_str} | "
            f"{time_str}\n"
        )

    prompt += ("\nTo get even more information on any of these ships, use the get_vessel_general_information tool with the correct mmsi")

    return prompt


def get_nearest_ships_helper(mmsi: str, number_ships: str) -> str:
    mmsi = int(mmsi)
    number_ships = int(number_ships)
    detections = get_all_latest_detections_helper()
    mmsis = get_all_mmsis()
    if mmsi not in mmsis:
        raise ValueError("MMSI not in vessels")
    primary_ship_location = get_vessel_latest_location_helper(mmsi)
    primary_lat = primary_ship_location['lat']
    primary_lon = primary_ship_location['lon']
    distances = []

    for detection in detections:
        if detection['mmsi'] == mmsi:
            continue
        lat = detection['lat']
        lon = detection['lon']
        if lat is None or lon is None:
            continue
        distance = haversine_distance_nm(primary_lat, primary_lon, lat, lon)
        distances.append({
            "distance": distance,
            "data": detection
        })

    distances.sort(key=lambda x: x['distance'])
    nearest_ships = distances[:number_ships]
    output = (
        f"The {number_ships} closest ships to {mmsi} are:\n\n"
        "MMSI       | Distance (nm) | Latitude   | Longitude   | SOG   | COG   | Time\n"
        "-----------+---------------+------------+-------------+-------+-------+----------\n"
    )

    for ship in nearest_ships:
        data = ship["data"]
        time_str = data["basedatetime"].strftime("%H:%M:%S") \
            if hasattr(data["basedatetime"], "strftime") \
            else str(data["basedatetime"])
        output += (
            f"{data['mmsi']:<10} | "
            f"{ship['distance']:<13.3f} | "
            f"{data['lat']:<10.5f} | "
            f"{data['lon']:<11.5f} | "
            f"{data['sog']:<5.1f} | "
            f"{data['cog']:<5.1f} | "
            f"{time_str}\n"
        )
    return output

def get_vessels_in_area_helper(lat: str, lon: str, distance_nm: str):
    lat = float(lat); lon = float(lon); distance_nm = float(distance_nm)
    detections = get_all_latest_detections_helper()
    sussy_bakas = []
    vessels_in_area = []
    for detection in detections:
        if not detection['lat'] or not detection['lon']:
            sussy_bakas.append(detection)
            continue
        distance = haversine_distance_nm(lat, lon, detection['lat'], detection['lon'])
        if distance < distance_nm:
            vessels_in_area.append(detection)
    if len(vessels_in_area) > 55:
        raise ValueError("Too many detections")

    prompt = (
        f"Results for vesstles within {distance_nm} of {lat}, {lon}\n\n"
        "MMSI       | Latitude | Longitude | SOG | COG  | Time \n"
        "-----------+----------+-----------+-----+------+----------\n"
    )

    for detection in vessels_in_area:
        time_str = detection['basedatetime'].strftime("%H:%M:%S") \
            if hasattr(detection["basedatetime"], "strftime") \
            else str(detection["basedatetime"])
        lat_str = f"{detection['lat']:7.2f}" if detection['lat'] is not None else " None  "
        lon_str = f"{detection['lon']:7.2f}" if detection['lon'] is not None else " None  "
        sog_str = f"{detection['sog']:4.1f}" if detection['sog'] is not None else "None"
        cog_str = f"{detection['cog']:5.1f}" if detection['cog'] is not None else "None "
        prompt += (
            f"{detection['mmsi']:<10} | "
            f"{lat_str} | "
            f"{lon_str} | "
            f"{sog_str} | "
            f"{cog_str} | "
            f"{time_str}\n"
        )
    prompt += ("\nList of MMSIs with latitude or longitude as None:\n")
    for baka in sussy_bakas:
        prompt += str(baka['mmsi'])
    prompt += ("\n\nTo get even more information on any of these ships, use the get_vessel_general_information tool with the correct mmsi")

    prompt += str(len(vessels_in_area))
    return prompt



"""These are only potentially useful if we decide to create a ibrary of important regions and ports. Otherwise, they are pretty much useless. We can rely on the AI to know what ports there are and its pretty good at that."""


def identify_maritime_region_helper(lat: float, lon: float) -> Optional[str]:
    """
    Identify the maritime region for given coordinates.
    
    Returns the most specific matching region.
    """
    matches = []
    
    for region_name, region_info in MARITIME_REGIONS.items():
        bounds = region_info["bounds"]
        
        # Handle regions crossing the date line
        if bounds["lon_min"] > bounds["lon_max"]:
            # Region crosses date line (e.g., Bering Sea)
            in_lon = lon >= bounds["lon_min"] or lon <= bounds["lon_max"]
        else:
            in_lon = bounds["lon_min"] <= lon <= bounds["lon_max"]
        
        in_lat = bounds["lat_min"] <= lat <= bounds["lat_max"]
        
        if in_lat and in_lon:
            # Calculate how specific/small the region is (smaller = more specific)
            area = (bounds["lat_max"] - bounds["lat_min"]) * abs(bounds["lon_max"] - bounds["lon_min"])
            matches.append((region_name, area))
    
    if matches:
        # Return most specific (smallest area) match
        matches.sort(key=lambda x: x[1])
        return matches[0][0]
    
    return None



def identify_nearest_port_helper(lat: float, lon: float) -> Tuple[str, float]:
    """Find the nearest major port and distance in nautical miles."""
    nearest = None
    min_distance = float('inf')
    
    for port_name, (port_lat, port_lon) in MAJOR_PORTS.items():
        distance = haversine_distance_nm(lat, lon, port_lat, port_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = port_name
    
    return nearest, min_distance



def identify_nearest_waterway_helper(lat: float, lon: float) -> Tuple[str, float]:
    """Find the nearest strategic waterway and distance in nautical miles."""
    nearest = None
    min_distance = float('inf')
    
    for waterway_name, (ww_lat, ww_lon) in STRATEGIC_WATERWAYS.items():
        distance = haversine_distance_nm(lat, lon, ww_lat, ww_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = waterway_name
    
    return nearest, min_distance

