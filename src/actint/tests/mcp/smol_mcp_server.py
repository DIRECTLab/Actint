from fastmcp import FastMCP
from actint.data_processing.query_database import query_vessels
from actint.tools.previous_locations import get_vehicle_locations, ship_following
import json


mcp = FastMCP("LocalServer")

@mcp.tool()
def get_vessel_mmsi(vessel_name: str) -> str:
    """Get the MMSI for a given vessel.

    Args:
        vessel_name: The name of the vessel (case insenstive)

    Returns:
        The MMSI number of the vessel as or an error message if no matches are found.
    """
    result = query_vessels({"vessel_name": vessel_name.upper()})
    if result and result[0]:
        return str(result[0][0])
    else:
        return f"ERROR: Could not find a vessel with the name '{vessel_name}'"
    
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

if __name__ == "__main__":
    mcp.run()