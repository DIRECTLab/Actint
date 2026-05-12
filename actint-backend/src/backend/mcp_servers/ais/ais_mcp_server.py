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
import sys

# Import tool functions from parent package
from backend.mcp_servers.ais.helpers.previous_locations import ship_following
from backend.mcp_servers.ais.helpers.ship_context import (
    get_vessel_general_information_helper,
    # get_location_context_helper as get_geolocation_context_helper,
    # get_distance_between as calc_distance_between,
    identify_maritime_region_helper,
    identify_nearest_port_helper,
    identify_nearest_waterway_helper,
)
from backend.mcp_servers.ais.helpers.fleet_information import (
    get_fleet_position_helper, ship_near_fleet_helper
)
from backend.mcp_servers.ais.helpers.vessel_query import (
    get_similar_mmsis,
    get_similar_vessel_names,
    get_similar_fleet_names,
    get_vessel_position_history_helper,
    get_vessel_latest_location_helper,
    get_vessel_mmsi_helper,
)
from backend.mcp_servers.ais.helpers.ship_going import (
    calculate_vector_and_distance_sum,
    get_possible_destinations_helper,
)
# from backend.data_processing.query_database import query_vessels

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

# ============================================================================
# FastMCP Server Setup
# ============================================================================
mcp = FastMCP("AIS Vessel Intelligence", "1.0.0")


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
Could not find the mmsi for vessel {vessel_name}.

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
        for mmsi in similar_mmsis:
            similar_mmsis_str += f"- {mmsi}\n"
        return f"""
Could not find vessel information for MMSI {mmsi}.

Similar MMSIs are: 
{similar_mmsis_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid mmsis.
"""
    except Exception as e:
        return "Error:\n" + e

    return general_information


# @mcp.tool() # I need to make this so that it doesn't give me a buttload of locations that caused autistic siezures with the AI
# def get_vessel_locations(mmsi: int | str) -> str:
#     """Get all recorded positions for a specific vessel identified by MMSI.
    
#     Args:
#         mmsi (int): Maritime Mobile Service Identity number of the vessel
    
#     Returns:
#         str: JSON list of vessel positions with coordinates, timestamps, and speed data
#     """
#     print("started")
#     try:
#         mmsi = int(mmsi)
#         locations = get_vessel_position_history(mmsi)
#         data = [
#             {
#                 "timestamp": loc.timestamp,
#                 "latitude": loc.lat,
#                 "longitude": loc.lon,
#                 "speed_over_ground": loc.sog,
#                 "course_over_ground": loc.cog,
#                 "heading": loc.heading,
#             }
#             for loc in locations
#         ]
#         result_data = { "mmsi": mmsi, "positions": data}
#         # return json.dumps(result_data, indent=2)
#         return result_data
#     except Exception as e:
#         return json.dumps({"error": str(e)})





@mcp.tool()
def identify_maritime_region(latitude: float | str, longitude: float | str) -> str:   # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
    """Identify which maritime region a lat/lon coordinate is in.
    
    Args:
        latitude (float): Latitude in decimal degrees
        longitude (float): Longitude in decimal degrees
    
    Returns:
        str: JSON with the name of the maritime region or "Unknown"
    """
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        region = identify_maritime_region_helper(latitude, longitude)
        result = {"region": region if region else "Unknown"}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def identify_nearest_port(latitude: float | str, longitude: float | str) -> str:    # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
    """Find the nearest major port to a given lat/lon.
    
    Args:
        latitude (float): Latitude in decimal degrees
        longitude (float): Longitude in decimal degrees
    
    Returns:
        str: JSON with port name and distance in nautical miles
    """
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        port_name, distance = identify_nearest_port_helper(latitude, longitude)
        result = {"port_name": port_name, "distance_nm": distance}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def identify_nearest_waterway(latitude: float | str, longitude: float | str) -> str:    # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
    """Find the nearest strategic waterway to a given lat/lon.
    
    Args:
        latitude (float): Latitude in decimal degrees
        longitude (float): Longitude in decimal degrees
    
    Returns:
        str: JSON with waterway name and distance in nautical miles
    """
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        waterway_name, distance = identify_nearest_waterway_helper(latitude, longitude)
        result = {"waterway_name": waterway_name, "distance_nm": distance}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Tools: Fleet Analysis
# ============================================================================

@mcp.tool()
def get_fleet_position(fleet_query: str) -> str:
    """Calculate the average position of a fleet of vessels.
    
    Args:
        fleet_name (str): Canonical name of the fleet
    
    Returns:
        str: JSON with fleet position (latitude and longitude)
    """
    try:
        lat, lon = get_fleet_position_helper(fleet_query)
        return f"The position of fleet {fleet_query} is lat {lat}, lon {lon}"
    except ValueError as e:
        similar_fleets = get_similar_fleet_names(str(fleet_query), 4)
        similar_fleets_str = ""
        for fleet_name in similar_fleets:
            similar_fleets_str += f"- {fleet_name}\n"
        return f"""
Could not find vessel information for fleet {fleet_query}.

Similar fleets are: 
{similar_fleets_str}

If this was a very minor typo, please proceed with the most accurate option, otherwise alert the user that their input was invalid and give them examples of valid fleets.
"""
    except Exception as e:
        return str(e)




# ============================================================================
# Tools: Destination Prediction
# ============================================================================

@mcp.tool()
def get_vessel_destination(mmsi: int | str, number_detections: int | str = 300) -> str:         # This might need to be modified to use the ship's heading and course over ground instead of this. 
    """Predict where a vessel is heading based on recent trajectory.
    
    Args:
        mmsi (int): MMSI of the vessel
        number_detections (int): Number of recent position detections to consider (default: 300)
    
    Returns:
        str: JSON with analysis result and note about trajectory analysis
    """
    try:
        mmsi = int(mmsi)
        number_detections = int(number_detections)
        calculate_vector_and_distance_sum(mmsi, number_detections)
        result = {
            "mmsi": mmsi,
            "note": "Destination analysis completed. See server logs for trajectory analysis."
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Tools: Database Introspection
# ============================================================================

def _quote_sqlite_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier (table/column name) using double quotes."""
    return '"' + (identifier or "").replace('"', '""') + '"'


@mcp.tool()
def get_database_info() -> str:                                                     # This should maybe be in a helper function or in the system prompt
    """Get basic SQLite database schema info (tables and column definitions).

    Returns:
        str: JSON object containing database path and a list of tables with columns.
    """
    try:
        sqlite_path = _resolve_sqlite_path()
        if not sqlite_path.exists():
            return json.dumps({"error": f"SQLite database not found at {sqlite_path}"})

        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name;"
        )
        table_names = [r[0] for r in cursor.fetchall()]

        tables: list[dict] = []
        for table_name in table_names:
            quoted = _quote_sqlite_identifier(table_name)
            cursor.execute(f"PRAGMA table_info({quoted});")
            # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
            columns = []
            for cid, name, col_type, notnull, dflt_value, pk in cursor.fetchall():
                columns.append(
                    {
                        "cid": cid,
                        "name": name,
                        "type": col_type,
                        "notnull": bool(notnull),
                        "default": dflt_value,
                        "pk": bool(pk),
                    }
                )

            tables.append({"name": table_name, "columns": columns})

        conn.close()

        return json.dumps(
            {
                "db_path": str(sqlite_path),
                "table_count": len(tables),
                "tables": tables,
            },
            indent=2,
        )
    except sqlite3.Error as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Introspection error: {str(e)}"})


# ============================================================================
# Tools: Database Query
# ============================================================================

@mcp.tool()
def query_database(sql_query: str, max_rows: int | str = 200) -> str:               
    """Execute a read-only SQL query against the AIS database and return results.
    
    Args:
        sql_query (str): Read-only SQL query to execute (SELECT / WITH ... SELECT)
        max_rows (int): Maximum number of rows to return (default: 200)
    
    Returns:
        str: JSON with query results and column names, or error message
    """
    try:
        max_rows = int(max_rows)
        query = (sql_query or "").strip()
        if not query:
            return json.dumps({"error": "sql_query is required"})

        # Guardrails: read-only, single-statement queries only
        ql = query.lower().lstrip()
        if not (ql.startswith("select") or ql.startswith("with")):
            return json.dumps({"error": "Only read-only SELECT queries are allowed"})

        forbidden = [
            "insert ", "update ", "delete ", "drop ", "alter ", "create ",
            "attach ", "detach ", "vacuum", "pragma", "reindex", "replace ",
            "truncate ",
        ]
        if any(tok in ql for tok in forbidden):
            return json.dumps({"error": "Query contains forbidden keywords"})

        # Disallow multi-statement execution; allow a single trailing semicolon
        if ";" in query.rstrip(";"):
            return json.dumps({"error": "Multiple SQL statements are not allowed"})

        if max_rows <= 0:
            max_rows = 200
        if max_rows > 5000:
            max_rows = 5000

        conn = sqlite3.connect(str(_resolve_sqlite_path()))
        cursor = conn.cursor()

        cursor.execute(query)
        
        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Fetch bounded results
        rows = cursor.fetchmany(max_rows + 1)
        
        # Convert rows to list of dicts
        result_list = []
        truncated = False
        if len(rows) > max_rows:
            truncated = True
            rows = rows[:max_rows]

        for row in rows:
            row_dict = {col: val for col, val in zip(columns, row)}
            result_list.append(row_dict)
        
        conn.close()
        
        result = {
            "columns": columns,
            "row_count": len(result_list),
            "truncated": truncated,
            "max_rows": max_rows,
            "rows": result_list
        }
        return json.dumps(result, indent=2)
    except sqlite3.Error as e:
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Query error: {str(e)}"})
    











# @mcp.tool()
# def ship_near_fleet(mmsi: int | str) -> str:                               # Ideally the AI should know if the ship is approximately "in the fleet" based on the data it can get for the ship's location and the fleet's location
#     """Check if a vessel is within fleet proximity (10 nautical miles).
    
#     Args:
#         mmsi (int): MMSI of the vessel to check
    
#     Returns:
#         str: String indicating if ship is in fleet or outside fleet proximity
#     """
#     try:
#         mmsi = int(mmsi)
#         result_str = ship_near_fleet_helper(mmsi)
#         return result_str
#     except Exception as e:
#         return "error: " + str(e)



# @mcp.tool()                                                                   #It is probably better to do a get_ship_general_information tool and have the name included
# def get_vessel_name(mmsi: int | str) -> str:
#     """Get the name of a vessel given its MMSI.
    
#     Args:
#         mmsi (int): Maritime Mobile Service Identity number of the vessel
    
#     Returns:
#         str: The name of the vessel or an error message
#     """
#     try:
#         mmsi = int(mmsi)
#         info = get_vessel_name_helper(mmsi)
#         if isinstance(info, dict):
#             return info.get("vessel_name", "Unknown")
#         else:
#             return "No Vessel with that MMSI."
#     except Exception as e:
#         print(e, file=sys.stderr)
#         return f"Error retrieving vessel name. That function does not seem to be working right now. You can try a different function or alert the user."

# @mcp.tool()
# def ship_following_analysis(mmsi1: int | str, mmsi2: int | str) -> str:
#     """Determine if one vessel has been following another vessel's path.
    
#     Args:
#         mmsi1 (int): MMSI of the initial vessel
#         mmsi2 (int): MMSI of the vessel to check if following
    
#     Returns:
#         str: Analysis string indicating how many times vessel 2 was near vessel 1
#     """
#     try:
#         mmsi1 = int(mmsi1)
#         mmsi2 = int(mmsi2)
#         result = ship_following(mmsi1, mmsi2)
#         return json.dumps({"analysis": result})
#     except Exception as e:
#         return json.dumps({"error": str(e)})

# ============================================================================
# Tools: Translation
# ============================================================================
 

# ============================================================================
# Tools: Geographic Context
# ============================================================================

# @mcp.tool()
# def get_location_context(latitude: float | str, longitude: float | str) -> str:
#     """Get geographic context for a lat/lon including maritime region, nearest ports, and strategic waterways.
    
#     Args:
#         latitude (float): Latitude in decimal degrees
#         longitude (float): Longitude in decimal degrees
    
#     Returns:
#         str: JSON with maritime region, nearest port, nearest waterway, and reverse geocoding info
#     """
#     try:
#         latitude = float(latitude)
#         longitude = float(longitude)
#         context = get_geolocation_context(latitude, longitude)
#         result = {
#             "latitude": latitude,
#             "longitude": longitude,
#             "maritime_region": context.maritime_region,
#             "nearest_port": {
#                 "name": context.nearest_port_name,
#                 "distance_nm": context.nearest_port_distance_nm,
#             } if context.nearest_port_name else None,
#             "nearest_waterway": {
#                 "name": context.nearest_waterway_name,
#                 "distance_nm": context.nearest_waterway_distance_nm,
#             } if context.nearest_waterway_name else None,
#             "reverse_geocoding": context.reverse_geocoding_result,
#         }
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return json.dumps({"error": str(e)})


# @mcp.tool()
# def get_distance_between(lat1: float | str, lon1: float | str, lat2: float | str, lon2: float | str) -> str:  # The AI ideally should be able to know the approximate distance between two different lattitude and longitude points
#     """Calculate distance and bearing between two geographic points.
    
#     Args:
#         lat1 (float): Latitude of first point
#         lon1 (float): Longitude of first point
#         lat2 (float): Latitude of second point
#         lon2 (float): Longitude of second point
    
#     Returns:
#         str: JSON with distance in nautical miles and bearing in degrees
#     """
#     try:
#         lat1 = float(lat1)
#         lon1 = float(lon1)
#         lat2 = float(lat2)
#         lon2 = float(lon2)
#         result = calc_distance_between(lat1, lon1, lat2, lon2)
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return json.dumps({"error": str(e)})



#@mcp.tool()
# def get_vessel_latest_location(mmsi: int | str) -> str:
#     """Get the most recent position of a vessel.
    
#     Args:
#         mmsi (int): Maritime Mobile Service Identity number of the vessel
    
#     Returns:
#         str: Information about the latest position of the vessel
#     """
#     try:
#         mmsi = int(mmsi)
#         location = get_vessel_latest_location_helper(mmsi)
#         if location:
#             result = "Current Vessel information:\n"
#             result += location
#             return result
#         else:
#             return "Error: No positions found for this vessel, this may be becuase of a wrong mmsi"
#     except Exception as e:
#         return "Error:\n" + str(e)


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
