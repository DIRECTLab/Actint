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
from fastmcp import FastMCP

from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes

from backend.mcp_servers.ais.helpers.ship_context import (
    get_vessel_general_information_helper,
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
    get_vessel_mmsi_helper,
)
from backend.mcp_servers.ais.helpers.ship_going import (
    calculate_vector_and_distance_sum,
)

# ============================================================================
# FastMCP Server Setup
# ============================================================================
mcp = FastMCP("AIS Vessel Intelligence", "1.0.0")


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


@mcp.tool()
def evaluate_vessel_risk() -> str:
    """Evaluate risk level of vessels based on dark behavior patterns."""
    try:
        # Placeholder implementation - replace with actual logic
        risk_evaluation = {
            "high_risk_vessels": 10,
            "medium_risk_vessels": 20,
            "low_risk_vessels": 12,
        }
        return json.dumps(risk_evaluation, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============================================================================
# Health & Info Endpoints
# ============================================================================

@mcp.tool()
def say_hello() -> str:
    """Simple tool to test connectivity and responsiveness of the MCP server."""
    message = "Hello! The AIS Vessel Intelligence MCP server is up and running."
    print("Printed Message:", message)#, file=sys.stderr)
    return message


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
# Tools: Using tools that Mario originally wrote
# ============================================================================
@mcp.tool()
def search_region_for_ships(region: str) -> dict:
    """Get information about dark vessels in a given region
    
    Args:
        region (str): Key of the region to search (e.g. "gulf_of_aden")

    Returns:
        str: String with information about concerning (dark?) vessels in the region

    """
    if region not in REGIONS:
        return {
            "success": False,
            "error": "INVALID_REGION",
            "available_regions": [
                {"key": k, "name": v["name"]}
                for k, v in REGIONS.items()
            ]
        }

    try:
        region_data = run_region(region)

        return {
            "success": True,
            "region": region,
            "data": region_data
        }

    except Exception as e:
        return {
            "success": False,
            "error": "EXECUTION_ERROR",
            "message": str(e)  # force safe serialization
        }

# ============================================================================
# Tools: Translation
# ============================================================================
 
@mcp.tool()
def get_vessel_mmsi(vessel_name: str) -> int:
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
def get_database_info() -> str:
    """Return a JSON summary of the database schema.

    This tool provides basic schema discovery for the AIS database, including
    table names and column definitions. Use it before writing queries when you
    need to inspect available structures.

    Returns:
        A JSON string describing the database schema, typically including tables
        and their columns.
    """

    try:
        with get_conn(DatabaseConnectionTypes.AIS) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        table_name,
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position;
                    """
                )

                rows = cursor.fetchall()

        tables: dict[str, list[dict[str, object]]] = {}
        for table_name, column_name, data_type, is_nullable, column_default in rows:
            if table_name not in tables:
                tables[table_name] = []

            tables[table_name].append(
                {
                    "name": column_name,
                    "type": data_type,
                    "nullable": is_nullable == "YES",
                    "default": column_default,
                }
            )

        result = {
            "table_count": len(tables),
            "tables": [
                {"name": table_name, "columns": columns}
                for table_name, columns in tables.items()
            ],
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Introspection error: {str(e)}"})


# ============================================================================
# Tools: Database Query
# ============================================================================

@mcp.tool()
def query_database(sql_query: str, max_rows: int | str = 200) -> str:
    """Execute a read-only SELECT query against the AIS database.

    This tool is intended for safe data retrieval only. It rejects any
    non-SELECT statement, multiple SQL statements, and queries containing
    forbidden schema-changing keywords.

    Args:
        sql_query: A single read-only SELECT query to execute.
        max_rows: Maximum number of rows to return. Values less than 1 default
            to 200. Values above 5000 are capped at 5000.

    Returns:
        A JSON string containing the query result with:
        - columns: List of column names
        - row_count: Number of rows returned
        - truncated: Whether additional rows were available
        - max_rows: Applied row limit
        - rows: List of row objects

        If the query is invalid or not allowed, returns a JSON object with an
        error field.
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
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "attach ",
            "detach ",
            "vacuum",
            "pragma",
            "reindex",
            "replace ",
            "truncate ",
        ]
        if any(tok in ql for tok in forbidden):
            return json.dumps({"error": "Query contains forbidden keywords"})

        if ";" in query.rstrip(";"):
            return json.dumps({"error": "Multiple SQL statements are not allowed"})

        if max_rows <= 0:
            max_rows = 200
        elif max_rows > 5000:
            max_rows = 5000

        with get_conn(DatabaseConnectionTypes.AIS) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)

                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )

                rows = cursor.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                rows = rows[:max_rows]

                result_rows = [
                    {col: val for col, val in zip(columns, row)}
                    for row in rows
                ]

        result = {
            "columns": columns,
            "row_count": len(result_rows),
            "truncated": truncated,
            "max_rows": max_rows,
            "rows": result_rows,
        }
        return json.dumps(result, indent=2)

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
