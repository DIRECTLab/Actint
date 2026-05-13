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
        f"To retrieve the next 8 positions:\n"
        f"  get_vessel_locations({mmsi}, {page + 1})"
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

    prompt += ("\nTo get even more information on any of these ships, run get_vessel_general_information() with the correct mmsi")

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
    prompt += ("\n\nTo get even more information on any of these ships, run get_vessel_general_information() with the correct mmsi")

    prompt += str(len(vessels_in_area))
    return prompt





















"""These might die"""


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


# @dataclass
# class LocationContext:
#     """Context information about a geographic location."""
#     lat: float
#     lon: float
    
#     # Reverse geocoding
#     country: Optional[str] = None
#     region: Optional[str] = None
#     city: Optional[str] = None
#     display_name: Optional[str] = None
    
#     # Maritime context
#     maritime_region: Optional[str] = None
#     nearest_port: Optional[str] = None
#     distance_to_port_nm: Optional[float] = None
#     nearest_waterway: Optional[str] = None
#     distance_to_waterway_nm: Optional[float] = None
    
#     # Position description
#     position_description: Optional[str] = None
    
#     def to_context_string(self) -> str:
#         """Format as context string for LLM."""
#         parts = [f"Location: {self.lat:.4f}°N, {abs(self.lon):.4f}°{'W' if self.lon < 0 else 'E'}"]
        
#         if self.display_name:
#             parts.append(f"Place: {self.display_name}")
#         elif self.country:
#             location_parts = [p for p in [self.city, self.region, self.country] if p]
#             if location_parts:
#                 parts.append(f"Place: {', '.join(location_parts)}")
        
#         if self.maritime_region:
#             parts.append(f"Maritime Region: {self.maritime_region}")
        
#         if self.nearest_port and self.distance_to_port_nm is not None:
#             parts.append(f"Nearest Major Port: {self.nearest_port} ({self.distance_to_port_nm:.1f} nm)")
        
#         if self.nearest_waterway and self.distance_to_waterway_nm is not None:
#             parts.append(f"Nearest Strategic Waterway: {self.nearest_waterway} ({self.distance_to_waterway_nm:.1f} nm)")
        
#         if self.position_description:
#             parts.append(f"Description: {self.position_description}")
        
#         return ". ".join(parts)
    
# def get_relative_position_helper(from_lat: float, from_lon: float, 
#                           to_lat: float, to_lon: float, 
#                           to_name: str) -> str:
#     """Get human-readable relative position description."""
#     distance = haversine_distance_nm(from_lat, from_lon, to_lat, to_lon)
#     bearing = calculate_bearing(from_lat, from_lon, to_lat, to_lon)
#     cardinal = bearing_to_cardinal(bearing)
    
#     # Inverse bearing (direction from reference point)
#     inverse_bearing = (bearing + 180) % 360
#     inverse_cardinal = bearing_to_cardinal(inverse_bearing)
    
#     return f"{distance:.0f} nm {inverse_cardinal} of {to_name}"


# # ============================================================================
# # Maritime Region Identification
# # ============================================================================



# def find_nearest_port_helper(lat: float, lon: float) -> Tuple[str, float]:
#     """Find the nearest major port and distance in nautical miles."""
#     nearest = None
#     min_distance = float('inf')
    
#     for port_name, (port_lat, port_lon) in MAJOR_PORTS.items():
#         distance = haversine_distance_nm(lat, lon, port_lat, port_lon)
#         if distance < min_distance:
#             min_distance = distance
#             nearest = port_name
    
#     return nearest, min_distance


# def find_nearest_waterway_helper(lat: float, lon: float) -> Tuple[str, float]:
#     """Find the nearest strategic waterway and distance in nautical miles."""
#     nearest = None
#     min_distance = float('inf')
    
#     for waterway_name, (ww_lat, ww_lon) in STRATEGIC_WATERWAYS.items():
#         distance = haversine_distance_nm(lat, lon, ww_lat, ww_lon)
#         if distance < min_distance:
#             min_distance = distance
#             nearest = waterway_name
    
#     return nearest, min_distance


# # ============================================================================
# # Reverse Geocoding
# # ============================================================================

# @lru_cache(maxsize=1000)
# def reverse_geocode_nominatim(lat: float, lon: float) -> dict:
#     """
#     Reverse geocode using OpenStreetMap Nominatim.
    
#     Results are cached to avoid repeated API calls.
#     """
#     if not HAS_GEOPY:
#         return {}
    
#     try:
#         geolocator = Nominatim(user_agent="actint_maritime_intel")
#         location = geolocator.reverse(f"{lat}, {lon}", language="en", timeout=5)
        
#         if location and location.raw:
#             address = location.raw.get("address", {})
#             return {
#                 "display_name": location.raw.get("display_name"),
#                 "country": address.get("country"),
#                 "region": address.get("state") or address.get("region"),
#                 "city": address.get("city") or address.get("town") or address.get("village"),
#             }
#     except (GeocoderTimedOut, GeocoderServiceError):
#         pass
#     except Exception:
#         pass
    
#     return {}


# @lru_cache(maxsize=1000)
# def reverse_geocode_offline(lat: float, lon: float) -> dict:
#     """
#     Reverse geocode using offline reverse_geocoder library.
    
#     Faster but less detailed than Nominatim.
#     """
#     if not HAS_REVERSE_GEOCODER:
#         return {}
    
#     try:
#         result = rg.search((lat, lon), mode=1)
#         if result:
#             r = result[0]
#             return {
#                 "city": r.get("name"),
#                 "region": r.get("admin1"),
#                 "country": r.get("cc"),
#             }
#     except Exception:
#         pass
    
#     return {}


# # ============================================================================
# # Main Tool Function
# # ============================================================================

# def get_location_context_helper(
#     mmsi: int,
#     use_online_geocoding: bool = False,
# ) -> LocationContext:
#     """
#     Get comprehensive context for a latitude/longitude location.
    
#     This is the main tool function that LLMs can call.
    
#     Args:
#         lat: Latitude in decimal degrees
#         lon: Longitude in decimal degrees  
#         use_online_geocoding: If True, use Nominatim API (slower but more detailed)
        
#     Returns:
#         LocationContext with all available information
#     """

#     current_position = get_latest_vessel_position_helper(mmsi)
#     lat = current_position['lat']
#     lon = current_position['lon']
#     context = LocationContext(lat=lat, lon=lon)
    
#     # Maritime region
#     context.maritime_region = identify_maritime_region_helper(lat, lon)
    
#     # Nearest port
#     port_name, port_dist = find_nearest_port_helper(lat, lon)
#     context.nearest_port = port_name
#     context.distance_to_port_nm = round(port_dist, 1)
    
#     # Nearest strategic waterway
#     waterway_name, waterway_dist = find_nearest_waterway_helper(lat, lon)
#     context.nearest_waterway = waterway_name
#     context.distance_to_waterway_nm = round(waterway_dist, 1)
    
#     # Reverse geocoding
#     if use_online_geocoding:
#         geo_info = reverse_geocode_nominatim(round(lat, 4), round(lon, 4))
#     else:
#         geo_info = reverse_geocode_offline(round(lat, 4), round(lon, 4))
    
#     if geo_info:
#         context.country = geo_info.get("country")
#         context.region = geo_info.get("region")
#         context.city = geo_info.get("city")
#         context.display_name = geo_info.get("display_name")
    
#     # Generate position description
#     if port_name and port_dist < 50:
#         context.position_description = f"Near {port_name}"
#     elif port_name:
#         port_lat, port_lon = MAJOR_PORTS[port_name]
#         context.position_description = get_relative_position_helper(lat, lon, port_lat, port_lon, port_name)
    
#     return context


# def get_location_context_string(lat: float, lon: float, use_online_geocoding: bool = False) -> str:
#     """
#     Get location context as a formatted string for LLM prompts.
    
#     Convenience wrapper around get_location_context().
#     """
#     context = get_location_context_helper(lat, lon, use_online_geocoding)
#     return context.to_context_string()


# def get_distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
#     """
#     Calculate distance and bearing between two points.
    
#     Tool for LLM to compare vessel positions.
#     """
#     distance = haversine_distance_nm(lat1, lon1, lat2, lon2)
#     bearing = calculate_bearing(lat1, lon1, lat2, lon2)
#     cardinal = bearing_to_cardinal(bearing)
    
#     return {
#         "distance_nm": round(distance, 1),
#         "bearing_degrees": round(bearing, 1),
#         "bearing_cardinal": cardinal,
#         "description": f"{distance:.1f} nm at bearing {bearing:.0f}° ({cardinal})",
#     }

