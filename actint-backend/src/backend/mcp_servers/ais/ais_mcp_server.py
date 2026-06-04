"""
MCP Server for AIS Vessel Intelligence Tools.

Standalone Model Context Protocol server that exposes AIS data tools
to be consumed by LLM applications via stdio.

Uses fastmcp for simplified server implementation.

Tools provided:
- Vessel location queries and temporal analysis
- Geographic context (maritime regions, ports, coordinates)
- Fleet analysis and proximity detection
- Destination prediction based on vessel heading
"""

import json
import sqlite3
import os
from pathlib import Path
from fastmcp import FastMCP

# Database path
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "ais.db"


def _resolve_sqlite_path() -> Path:
    """Resolve SQLite path, allowing benchmark overrides via env var."""
    override = os.getenv("ACTINT_SQLITE_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return SQLITE_PATH

# Import tool functions from parent package
from backend.mcp_servers.ais.helpers.dark_vessel_helper import (
    query_vessel,
    get_fishy_vessel_locations_helper,
    find_fishy_clusters,
)
from backend.mcp_servers.ais.helpers.ship_context import (
    get_vessel_general_information_helper,
    get_vessel_locations_helper,
    get_nearest_ships_helper,
    # get_vessels_last_seen_helper,
    get_vessels_in_area_helper,
)
from backend.mcp_servers.ais.helpers.fleet_information import (
    get_fleet_position_helper, get_fleets_information_helper, get_vessels_in_fleet_helper
)
from backend.mcp_servers.ais.helpers.similartiy import (
    get_similar_mmsis,
    get_similar_vessel_names,
    get_similar_fleet_names,
)

# ============================================================================
# FastMCP Server Setup
# ============================================================================

mcp = FastMCP("AIS Vessel Intelligence", "1.0.0")

# ============================================================================
# General Information
# ============================================================================

""" This isn't very good, there is too much output, there are too many ships"""

# @mcp.tool()
# def get_vessels_last_seen():
#     try: 
#         return get_vessels_last_seen_helper()
#     except Exception as e:
#         return "Error:\n" + str(e)


# ============================================================================
# Fishy Vessel Analysis Tools
# ============================================================================

@mcp.tool()
def summarise_fishy_vessels_in_region(region: str):
    """Get a number of vessels in a region marked as fishy and information about clusters of fishy vessels."""

    cluster_size = 5 #TODO: Figure out what this should actually be
    vessel_locations = get_fishy_vessel_locations_helper(region)
    number_of_vessels = len(vessel_locations)
    cluster_info = detect_fishy_clusters(region)

    result = f"Region {region} has {number_of_vessels} vessels marked as suspicious." + cluster_info
    return result


@mcp.tool()
def evaluate_vessel_fishiness():
    """Look for a vessel in the fishy vessels database and return if a vessel is fishy and why."""
    result = query_vessel(vessel_name)
    result = f"Vessel {vessel_name} has a dark risk score of {result[0][1]} and the following anomaly flags: {result[0][2]}"
    return result


@mcp.tool()
def get_fishy_vessel_locations(region):
    """Get the most recent locations of vessels in a region marked as suspicious and their tradjectories."""
    result = get_fishy_vessel_locations_helper(region)
    # get info about vessels in the region
    # strip down the info to names and lat/lon
    # return that info in a format that is easy for the llm to use
    for detection in result:
        print(Fore.LIGHTBLUE_EX + str(detection) + Fore.RESET)
    return result


@mcp.tool()
def detect_fishy_clusters(region):
    """Detect clusters of vessels in a region that may indicate suspicious activity."""
    # we might get rid of this tool and just use the summarise function instead. we'll see which the llm works better with?
    cluster_size = 5
    vessel_locations = get_fishy_vessel_locations_helper(region)
    clusters = []
    for detection in vessel_locations:
        clusters.append(find_fishy_clusters(detection['mmsi'], str(cluster_size), region))
    print(Fore.LIGHTBLUE_EX + f"Found {len(clusters)} clusters of fishy vessels in region {region}." + Fore.RESET)
    return f"Found {len(clusters)} clusters of fishy vessels in region {region}."


@mcp.tool()
def summarise_insecure_areas(region: str):
    """Give an analysis on what areas experience the most fishy vessel presence."""
    result = get_fishy_hotspots_helper(region)
    return result


@mcp.tool()
def re_evaluate_region(region):
    """Re-run region analysis for fishy vessels."""
    
    return f"Region {region} has been re-evaluated for fishy vessels."


# ============================================================================
# Dark Vessel Detection Tools
# ============================================================================

@mcp.tool()
def run_dark_vessel_startup() -> str:
    """Run the dark vessel startup script to analyze dark vessel patterns."""
    dark_vessel_startup.run()


@mcp.tool()
def summarise_dark_vessels() -> str:
    """Summarise information about dark vessels in the database."""
    try:
        # Placeholder implementation - replace with actual logic
        summary = {
            "total_dark_vessels": 42,
            "recent_dark_vessels": 5,
            "regions_with_dark_vessels": ["Gulf of Aden", "Strait of Malacca"],
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Health & Info Endpoints
# ============================================================================

""" This isn't very good, there is too much output, there are too many ships"""

# @mcp.tool()
# def get_vessels_last_seen():
#     try: 
#         return get_vessels_last_seen_helper()
#     except Exception as e:
#         return "Error:\n" + str(e)

@mcp.tool()
def get_vessel_current_position(mmsi: int | str) -> str:
    """Get the most recent position of a vessel.
    
    Args:
        mmsi (int): Maritime Mobile Service Identity number of the vessel
    
    Returns:
        str: JSON object with current position, speed, heading, and timestamp
    """
    try:
        mmsi = int(mmsi)
        locations = get_vehicle_locations(mmsi)
        if locations:
            loc = locations[0]  # Most recent
            result = {
                "mmsi": loc.mmsi,
                "vessel_name": loc.vessel_name,
                "timestamp": loc.timestamp,
                "latitude": loc.lat,
                "longitude": loc.lon,
                "speed_over_ground": loc.sog,
                "course_over_ground": loc.cog,
                "heading": loc.heading,
            }
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": "No positions found for this vessel"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def ship_following_analysis(mmsi1: int | str, mmsi2: int | str) -> str:
    """Determine if one vessel has been following another vessel's path.
    
    Args:
        mmsi1 (int): MMSI of the initial vessel
        mmsi2 (int): MMSI of the vessel to check if following
    
    Returns:
        str: Analysis string indicating how many times vessel 2 was near vessel 1
    """
    try:
        mmsi1 = int(mmsi1)
        mmsi2 = int(mmsi2)
        result = ship_following(mmsi1, mmsi2)
        return json.dumps({"analysis": result})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============================================================================
# Fishy Vessel Analysis Tools
# ============================================================================

@mcp.tool()
def summarise_fishy_vessels_in_region():
    """Get a number of vessels in a region marked as fishy and information about clusters of fishy vessels."""
    cluster_size = 5 # Can be adjusted based on more realistic use cases if needed
    vessel_locations = get_fishy_vessel_locations_helper()
    number_of_vessels = len(vessel_locations)
    cluster_info = detect_fishy_clusters()

    return json.dumps({
        "number_of_fishy_vessels": number_of_vessels,
        "cluster_info": cluster_info
    }, indent=2)


@mcp.tool()
def evaluate_vessel_fishiness(mmsi: str):
    """Look for a vessel in the suspicious vessels database and return if a vessel is suspicious and why."""
    result = query_vessel(mmsi)
    return json.dumps({"vessel fishiness": refsult}, indent=2)


@mcp.tool()
def get_fishy_vessel_locations():
    """Get the most recent locations of vessels in a region marked as suspicious and their tradjectories."""
    result = get_fishy_vessel_locations_helper()
    return json.dumps({"vessel_locations": result}, indent=2)


@mcp.tool()
def detect_fishy_clusters():
    """Detect clusters of vessels in a region that may indicate suspicious activity."""
    # we might get rid of this tool and just use the summarise function instead. we'll see which the llm works better with?
    cluster_size = 5
    vessel_locations = get_fishy_vessel_locations_helper()
    clusters = []
    for detection in vessel_locations:
        clusters.append(find_fishy_clusters(detection['mmsi'], str(cluster_size), region))
    return json.dumps({"clusters": clusters}, indent=2)


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@mcp.tool()
def say_hello() -> str:
    """Simple tool to test connectivity and responsiveness of the MCP server."""
    message = "Hello! The AIS Vessel Intelligence MCP server is up and running."
    print("Printed Message:", message)#, file=sys.stderr)
    return message


# @mcp.tool()
# def get_vessel_current_position(mmsi: int | str) -> str:
#     """Get the most recent position of a vessel.
    
#     Args:
#         mmsi (int): Maritime Mobile Service Identity number of the vessel
    
#     Returns:
#         str: JSON object with current position, speed, heading, and timestamp
#     """
#     try:
#         mmsi = int(mmsi)
#         locations = get_vehicle_locations(mmsi)
#         if locations:
#             loc = locations[0]  # Most recent
#             result = {
#                 "mmsi": loc.mmsi,
#                 "vessel_name": loc.vessel_name,
#                 "timestamp": loc.timestamp,
#                 "latitude": loc.lat,
#                 "longitude": loc.lon,
#                 "speed_over_ground": loc.sog,
#                 "course_over_ground": loc.cog,
#                 "heading": loc.heading,
#             }
#             return json.dumps(result, indent=2)
#         else:
#             return json.dumps({"error": "No positions found for this vessel"})
#     except Exception as e:
#         return json.dumps({"error": str(e)})


@mcp.tool()
def ship_following_analysis(mmsi1: int | str, mmsi2: int | str) -> str:
    """Determine if one vessel has been following another vessel's path.
    
    Args:
        mmsi1 (int): MMSI of the initial vessel
        mmsi2 (int): MMSI of the vessel to check if following
    
    Returns:
        str: Analysis string indicating how many times vessel 2 was near vessel 1
    """
    try:
        mmsi1 = int(mmsi1)
        mmsi2 = int(mmsi2)
        result = ship_following(mmsi1, mmsi2)
        return json.dumps({"analysis": result})
    except Exception as e:
        return json.dumps({"error": str(e)})
    

# ============================================================================
# Tools: Translation
# ============================================================================
@mcp.tool()
def get_vessel_mmsi(vessel_name: str) -> str:
    """Get the MMSI for a given vessel.

    Args:
        vessel_name (str): The name of the vessel (case insenstive)

    Returns:
        int: The MMSI number of the vessel as an int. Returns an error message if no vessels match the given name.
    """
    try:
        vessel_mmsi = get_vessel_mmsi_helper(vessel_name)
        if vessel_mmsi:
            return f"The mmsi for vessel {vessel_name} is {vessel_mmsi}."
    except ValueError as e:
        similar_names = get_similar_vessel_names(vessel_name, 4)
        similar_names_str = ""
        for name in similar_names:
            similar_names_str += f"- {name}\n"
        
        return f"""
Could not find the mmsi for vessel {vessel_name}

Vessels with the most similar names are:
{similar_names_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid vessel names.
"""


@mcp.tool()
def get_vessel_general_information(mmsi: str) -> str:
    """Get information about a vessel. This includes the name, time and most rescent location, heading, cargo, course and speed overground, ect.
    
    Args: 
        mmsi (int): Maritime Mobile Service Identity number of the vessel
        
    Returns: 
        str: Informatioon about the vessel
    """
    try:
        mmsi = int(mmsi)
        general_information = get_vessel_general_information_helper(mmsi)

    except ValueError as e:
        similar_mmsis = get_similar_mmsis(str(mmsi), 4)
        similar_mmsis_str = ""
        for similar_mmsi in similar_mmsis:
            similar_mmsis_str += f"- {similar_mmsi}\n"
        return f"""
Could not find vessel information for MMSI {mmsi}.

Similar MMSIs are: 
{similar_mmsis_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid mmsis.
"""
    except Exception as e:
        return "Error:\n" + e

    return general_information


@mcp.tool() # I need to make this so that it doesn't give me a buttload of locations that caused autistic siezures with the AI
def get_vessel_locations(mmsi: str, page: str) -> str:
    """Get all recorded positions for a specific vessel identified by MMSI.
    
    Args:
        mmsi (str): Maritime Mobile Service Identity number of the vessel
        page (str): Page number of detections. Start with '1'.
    
    Returns:
        A list of detections
    """
    print("started")
    try:
        result = get_vessel_locations_helper(mmsi, page)

        return result
    except ValueError as e:
        similar_mmsis = get_similar_mmsis(str(mmsi), 4)
        similar_mmsis_str = ""
        for similar_mmsi in similar_mmsis:
            similar_mmsis_str += f"- {similar_mmsi}\n"
        return f"""
Could not find vessel information for MMSI {mmsi}.

Similar MMSIs are: 
{similar_mmsis_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid mmsis.
"""
    except Exception as e:
        return "Error:\n" + str(e)



@mcp.tool()
def get_nearest_ships(mmsi: str, number_ships: str):
    """Finds the closes ships to the ship with the provided mmsi and their distances.
    
    Args: 
        mmsi (str): mmsi of the primary ship
        number_ships: Number of closest ships that should be returned

    Returns:
        str: Ship names and distances.
    """
    try: 
        result = get_nearest_ships_helper(mmsi, number_ships)
        return result
    except ValueError as e:
        similar_mmsis = get_similar_mmsis(str(mmsi), 4)
        similar_mmsis_str = ""
        for similar_mmsi in similar_mmsis:
            similar_mmsis_str += f"- {similar_mmsi}\n"
        return f"""
Could not find vessel information for MMSI {mmsi}.

Similar MMSIs are: 
{similar_mmsis_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid mmsis.
"""
    except Exception as e:
        return "Error:\n" + str(e)



# ============================================================================
# Tools: Fleet Analysis
# ============================================================================

@mcp.tool()
def get_fleet_position(fleet_name: str) -> str:
    """Calculate the average position of a fleet of vessels.
    
    Args:
        fleet_name (str): Canonical name of the fleet
    
    Returns:
        str: fleet position (latitude and longitude)
    """
    try:
        lat, lon = get_fleet_position_helper(fleet_name)
        return f"The position of fleet {fleet_name} is lat {lat}, lon {lon}"
    except ValueError as e:
        similar_fleets = get_similar_fleet_names(str(fleet_name), 4)
        similar_fleets_str = ""
        for fleet_name in similar_fleets:
            similar_fleets_str += f"- {fleet_name}\n"
        return f"""
Could not find vessel information for fleet {fleet_name}.

Similar fleets are:
{similar_fleets_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid fleets.
"""
    except Exception as e:
        return "Error: " + str(e)


@mcp.tool()
def get_fleets_information():
    """Gets information about all the fleets
    
    Args:
        None
    
    Returns: str: Information about the fleets
    """
    try:
        return get_fleets_information_helper()
    except Exception as e:
        return "Error:\n" + str(e)


@mcp.tool()
def get_vessels_in_fleet(fleet_name: str) -> str:
    """Gets the mmsis of all the vessels in a fleet
    
    Args:
        fleet_name (str): Canonical name of the fleet
        
    Returns: 
        str: MMSIs of all ships in the fleet
    """

    try:
        return get_vessels_in_fleet_helper(fleet_name)
    except ValueError as e:
        similar_fleets = get_similar_fleet_names(str(fleet_name), 4)
        similar_fleets_str = ""
        for fleet in similar_fleets:
            similar_fleets_str += f"- {fleet}\n"
        return f"""
Could not find vessel information for fleet {fleet_name}.
"""


# ============================================================================
# Tools: Geographic Queries
# ============================================================================

@mcp.tool()
def get_vessels_in_area(lat: str, lon: str, radius_nm: str):
    """Retrieves the mmsis of all the vessels in the radius of a certain point.
    
    Args:
        lat: Latitude of the point
        lon: Longitude of the point
    
    Returns: 
        str: List of MMSIs in within the radius of the point
    """
    try:
        return get_vessels_in_area_helper(lat, lon, radius_nm)
    except Exception as e: 
        return "Error:\n" + str(e)


def run_dark_vessel_tests():
    # print("summarise_fishy_vessels_in_region: " + summarise_fishy_vessels_in_region("brazil_eez"))
    # print("evaluate_vessel_fishiness: ", evaluate_vessel_fishiness("jane"))
    # print("get_fishy_vessel_locations: ", get_fishy_vessel_locations("brazil_eez"))
    # print("detect_fishy_clusters: ", detect_fishy_clusters("brazil_eez"))
    print("summarise_insecure_areas: ", summarise_insecure_areas("brazil_eez"))
    # print("re_evaluate_region: ", re_evaluate_region("brazil_eez"))

# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    # mcp.run() # TODO: Uncomment before pushing
    run_dark_vessel_tests() #TODO: Remove before pushing
