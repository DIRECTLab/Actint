"""
MCP server for the map specialist agent.

This server exposes maritime/geospatial context tools only.
It does not expose SQL querying or vessel trajectory analytics.
"""

import json

from fastmcp import FastMCP

from actint.tools.lat_lon_context import (
    find_nearest_port as find_closest_port,
    find_nearest_waterway as find_closest_waterway,
    get_distance_between as calc_distance_between,
    get_location_context as get_geolocation_context,
    identify_maritime_region as identify_region,
)

mcp = FastMCP("AIS Map Specialist", "1.0.0")


@mcp.tool()
def get_location_context(latitude: float | str, longitude: float | str) -> str:
    """Get maritime context for a coordinate.

    Args:
        latitude (float): Latitude in decimal degrees.
        longitude (float): Longitude in decimal degrees.

    Returns:
        str: JSON object with maritime region, nearest port/waterway, and reverse geocoding.
    """
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        context = get_geolocation_context(latitude, longitude)
        result = {
            "latitude": latitude,
            "longitude": longitude,
            "maritime_region": context.maritime_region,
            "nearest_port": {
                "name": context.nearest_port,
                "distance_nm": context.distance_to_port_nm,
            }
            if context.nearest_port
            else None,
            "nearest_waterway": {
                "name": context.nearest_waterway,
                "distance_nm": context.distance_to_waterway_nm,
            }
            if context.nearest_waterway
            else None,
            "reverse_geocoding": {
                "display_name": context.display_name,
                "country": context.country,
                "region": context.region,
                "city": context.city,
            },
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_distance_between(
    lat1: float | str,
    lon1: float | str,
    lat2: float | str,
    lon2: float | str,
) -> str:
    """Calculate distance and bearing between two points.

    Returns:
        str: JSON with nautical-mile distance and bearing.
    """
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        result = calc_distance_between(lat1, lon1, lat2, lon2)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def identify_maritime_region(latitude: float | str, longitude: float | str) -> str:
    """Identify the maritime region for a coordinate."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        region = identify_region(latitude, longitude)
        return json.dumps({"region": region if region else "Unknown"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_nearest_port(latitude: float | str, longitude: float | str) -> str:
    """Find nearest major port for a coordinate."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        port_name, distance = find_closest_port(latitude, longitude)
        return json.dumps({"port_name": port_name, "distance_nm": distance}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_nearest_waterway(latitude: float | str, longitude: float | str) -> str:
    """Find nearest strategic waterway for a coordinate."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        waterway_name, distance = find_closest_waterway(latitude, longitude)
        return json.dumps(
            {"waterway_name": waterway_name, "distance_nm": distance},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
