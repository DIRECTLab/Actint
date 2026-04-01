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
from pathlib import Path
from fastmcp import FastMCP

# Database path
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "ais.db"

# Import tool functions from parent package
from actint.tools.previous_locations import get_vehicle_locations, ship_following
from actint.tools.lat_lon_context import (
    get_location_context as get_geolocation_context,
    get_distance_between as calc_distance_between,
    identify_maritime_region as identify_region,
    find_nearest_port as find_closest_port,
    find_nearest_waterway as find_closest_waterway,
)
from actint.tools.close_to_fleet import calculate_fleet_position as calc_fleet_position, is_ship_in_fleet as check_ship_in_fleet
from actint.tools.ship_going import (
    calculate_vector_and_distance_sum,
    get_possible_destinations,
)

from actint.data_processing.query_database import query_vessels
# ============================================================================
# FastMCP Server Setup
# ============================================================================

mcp = FastMCP("AIS Vessel Intelligence", "1.0.0")


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@mcp.tool()
def get_vessel_locations(mmsi: int) -> str:
    """Get all recorded positions for a specific vessel identified by MMSI.
    
    Args:
        mmsi: Maritime Mobile Service Identity number of the vessel
    
    Returns:
        JSON list of vessel positions with coordinates, timestamps, and speed data
    """
    try:
        locations = get_vehicle_locations(mmsi)
        result_data = [
            {
                "mmsi": loc.mmsi,
                "vessel_name": loc.vessel_name,
                "timestamp": loc.timestamp,
                "latitude": loc.lat,
                "longitude": loc.lon,
                "speed_over_ground": loc.sog,
                "course_over_ground": loc.cog,
                "heading": loc.heading,
            }
            for loc in locations
        ]
        return json.dumps(result_data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_vessel_current_position(mmsi: int) -> str:
    """Get the most recent position of a vessel.
    
    Args:
        mmsi: Maritime Mobile Service Identity number of the vessel
    
    Returns:
        JSON object with current position, speed, heading, and timestamp
    """
    try:
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
def ship_following_analysis(mmsi1: int, mmsi2: int) -> str:
    """Determine if one vessel has been following another vessel's path.
    
    Args:
        mmsi1: MMSI of the initial vessel
        mmsi2: MMSI of the vessel to check if following
    
    Returns:
        Analysis string indicating how many times vessel 2 was near vessel 1
    """
    try:
        result = ship_following(mmsi1, mmsi2)
        return json.dumps({"analysis": result})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============================================================================
# Tools: Query Processing
# ============================================================================
 
@mcp.tool()
def get_vessel_mmsi(vessel_name: str) -> int:
    """Get the MMSI for a given vessel.

    Args:
        vessel_name: The name of the vessel (case insenstive)

    Returns:
        The MMSI number of the vessel as an int. Returns -1 if no vessels match the given name.
    """
    result = query_vessels({"vessel_name": vessel_name.upper()})
    if result and result[0]:
        return result[0][0]
    else:
        return -1

# ============================================================================
# Tools: Geographic Context
# ============================================================================

@mcp.tool()
def get_location_context(latitude: float, longitude: float) -> str:
    """Get geographic context for a lat/lon including maritime region, nearest ports, and strategic waterways.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    
    Returns:
        JSON with maritime region, nearest port, nearest waterway, and reverse geocoding info
    """
    try:
        context = get_geolocation_context(latitude, longitude)
        result = {
            "latitude": latitude,
            "longitude": longitude,
            "maritime_region": context.maritime_region,
            "nearest_port": {
                "name": context.nearest_port_name,
                "distance_nm": context.nearest_port_distance_nm,
            } if context.nearest_port_name else None,
            "nearest_waterway": {
                "name": context.nearest_waterway_name,
                "distance_nm": context.nearest_waterway_distance_nm,
            } if context.nearest_waterway_name else None,
            "reverse_geocoding": context.reverse_geocoding_result,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Calculate distance and bearing between two geographic points.
    
    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
    
    Returns:
        JSON with distance in nautical miles and bearing in degrees
    """
    try:
        result = calc_distance_between(lat1, lon1, lat2, lon2)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def identify_maritime_region(latitude: float, longitude: float) -> str:
    """Identify which maritime region a lat/lon coordinate is in.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    
    Returns:
        JSON with the name of the maritime region or "Unknown"
    """
    try:
        region = identify_region(latitude, longitude)
        result = {"region": region if region else "Unknown"}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_nearest_port(latitude: float, longitude: float) -> str:
    """Find the nearest major port to a given lat/lon.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    
    Returns:
        JSON with port name and distance in nautical miles
    """
    try:
        port_name, distance = find_closest_port(latitude, longitude)
        result = {"port_name": port_name, "distance_nm": distance}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_nearest_waterway(latitude: float, longitude: float) -> str:
    """Find the nearest strategic waterway to a given lat/lon.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    
    Returns:
        JSON with waterway name and distance in nautical miles
    """
    try:
        waterway_name, distance = find_closest_waterway(latitude, longitude)
        result = {"waterway_name": waterway_name, "distance_nm": distance}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Tools: Fleet Analysis
# ============================================================================

@mcp.tool()
def calculate_fleet_position(fleet_name: str) -> str:
    """Calculate the average position of a fleet of vessels.
    
    Args:
        fleet_name: Canonical name of the fleet
    
    Returns:
        JSON with fleet position (latitude and longitude)
    """
    try:
        lat, lon = calc_fleet_position(fleet_name)
        result = {
            "fleet_name": fleet_name,
            "fleet_position": {"latitude": lat, "longitude": lon}
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def is_ship_in_fleet(mmsi: int) -> str:
    """Check if a vessel is within fleet proximity (10 nautical miles).
    
    Args:
        mmsi: MMSI of the vessel to check
    
    Returns:
        String indicating if ship is in fleet or outside fleet proximity
    """
    try:
        result_str = check_ship_in_fleet(mmsi)
        return json.dumps({"proximity_check": result_str})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Tools: Destination Prediction
# ============================================================================

@mcp.tool()
def get_vessel_destination(mmsi: int, number_detections: int = 300) -> str:
    """Predict where a vessel is heading based on recent trajectory.
    
    Args:
        mmsi: MMSI of the vessel
        number_detections: Number of recent position detections to consider (default: 300)
    
    Returns:
        JSON with analysis result and note about trajectory analysis
    """
    try:
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
    """Get basic SQLite database schema info (tables and column definitions).

    Returns:
        JSON object containing database path and a list of tables with columns.
    """
    try:
        if not SQLITE_PATH.exists():
            return json.dumps({"error": f"SQLite database not found at {SQLITE_PATH}"})

        conn = sqlite3.connect(str(SQLITE_PATH))
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
                "db_path": str(SQLITE_PATH),
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
def query_database(sql_query: str, max_rows: int = 200) -> str:
    """Execute a read-only SQL query against the AIS database and return results.
    
    Args:
        sql_query: Read-only SQL query to execute (SELECT / WITH ... SELECT)
        max_rows: Maximum number of rows to return (default: 200)
    
    Returns:
        JSON with query results and column names, or error message
    """
    try:
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

        conn = sqlite3.connect(str(SQLITE_PATH))
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


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()
