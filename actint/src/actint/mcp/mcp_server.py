"""
MCP Server for AIS Vessel Intelligence Tools.

Standalone Model Context Protocol server that exposes AIS data tools
to be consumed by LLM applications via HTTP.

Tools provided:
- Vessel location queries and temporal analysis
- Geographic context (maritime regions, ports, coordinates)
- Fleet analysis and proximity detection
- Destination prediction based on vessel heading
"""

import os
import json
from datetime import datetime, timedelta
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import Server
from pydantic import BaseModel
import mcp.types as types

# Import tool functions from parent package
from actint.tools.previous_locations import get_vehicle_locations, ship_following
from actint.tools.lat_lon_context import (
    get_location_context,
    get_distance_between,
    identify_maritime_region,
    find_nearest_port,
    find_nearest_waterway,
)
from actint.tools.close_to_fleet import calculate_fleet_position, is_ship_in_fleet
from actint.tools.ship_going import (
    calculate_vector_and_distance_sum,
    get_possible_destinations,
)


# ============================================================================
# MCP Server Setup
# ============================================================================

class VesselData(BaseModel):
    """Response model for vessel position data."""
    mmsi: int
    vessel_name: str
    timestamp: str
    latitude: float
    longitude: float
    speed_over_ground: float
    course_over_ground: float
    heading: float


class LocationContextData(BaseModel):
    """Response model for location context."""
    latitude: float
    longitude: float
    maritime_region: str | None
    nearest_port: dict | None
    nearest_waterway: dict | None
    distance_to_port: float | None


# Server instance
server = Server("ais-vessel-intelligence")


# ============================================================================
# Tool: Get Vessel Locations
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools."""
    return [
        types.Tool(
            name="get_vessel_locations",
            description="Get all recorded positions for a specific vessel identified by MMSI",
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "integer",
                        "description": "Maritime Mobile Service Identity number of the vessel"
                    }
                },
                "required": ["mmsi"]
            }
        ),
        types.Tool(
            name="get_vessel_current_position",
            description="Get the most recent position of a vessel",
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "integer",
                        "description": "Maritime Mobile Service Identity number of the vessel"
                    }
                },
                "required": ["mmsi"]
            }
        ),
        types.Tool(
            name="ship_following_analysis",
            description="Determine if one vessel has been following another vessel's path",
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi1": {
                        "type": "integer",
                        "description": "MMSI of the initial vessel"
                    },
                    "mmsi2": {
                        "type": "integer",
                        "description": "MMSI of the vessel to check if following"
                    }
                },
                "required": ["mmsi1", "mmsi2"]
            }
        ),
        types.Tool(
            name="get_location_context",
            description="Get geographic context for a lat/lon including maritime region, nearest ports, and strategic waterways",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        types.Tool(
            name="get_distance_between",
            description="Calculate distance and bearing between two geographic points",
            inputSchema={
                "type": "object",
                "properties": {
                    "lat1": {
                        "type": "number",
                        "description": "Latitude of first point"
                    },
                    "lon1": {
                        "type": "number",
                        "description": "Longitude of first point"
                    },
                    "lat2": {
                        "type": "number",
                        "description": "Latitude of second point"
                    },
                    "lon2": {
                        "type": "number",
                        "description": "Longitude of second point"
                    }
                },
                "required": ["lat1", "lon1", "lat2", "lon2"]
            }
        ),
        types.Tool(
            name="identify_maritime_region",
            description="Identify which maritime region a lat/lon coordinate is in",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        types.Tool(
            name="find_nearest_port",
            description="Find the nearest major port to a given lat/lon",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        types.Tool(
            name="find_nearest_waterway",
            description="Find the nearest strategic waterway to a given lat/lon",
            inputSchema={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        ),
        types.Tool(
            name="calculate_fleet_position",
            description="Calculate the average position of a fleet of vessels",
            inputSchema={
                "type": "object",
                "properties": {
                    "fleet_name": {
                        "type": "string",
                        "description": "Canonical name of the fleet"
                    }
                },
                "required": ["fleet_name"]
            }
        ),
        types.Tool(
            name="is_ship_in_fleet",
            description="Check if a vessel is within fleet proximity (10 nautical miles)",
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "integer",
                        "description": "MMSI of the vessel to check"
                    }
                },
                "required": ["mmsi"]
            }
        ),
        types.Tool(
            name="get_vessel_destination",
            description="Predict where a vessel is heading based on recent trajectory",
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi": {
                        "type": "integer",
                        "description": "MMSI of the vessel"
                    },
                    "number_detections": {
                        "type": "integer",
                        "description": "Number of recent position detections to consider (default: 300)"
                    }
                },
                "required": ["mmsi"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent] | types.ImageContent | types.ErrorContent:
    """Handle tool calls from the client."""
    try:
        if name == "get_vessel_locations":
            mmsi = arguments["mmsi"]
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
            return [types.TextContent(type="text", text=json.dumps(result_data, indent=2))]
        
        elif name == "get_vessel_current_position":
            mmsi = arguments["mmsi"]
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
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                return [types.TextContent(type="text", text="No positions found for this vessel")]
        
        elif name == "ship_following_analysis":
            mmsi1 = arguments["mmsi1"]
            mmsi2 = arguments["mmsi2"]
            result = ship_following(mmsi1, mmsi2)
            return [types.TextContent(type="text", text=result)]
        
        elif name == "get_location_context":
            lat = arguments["latitude"]
            lon = arguments["longitude"]
            context = get_location_context(lat, lon)
            
            result = {
                "latitude": lat,
                "longitude": lon,
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
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_distance_between":
            lat1 = arguments["lat1"]
            lon1 = arguments["lon1"]
            lat2 = arguments["lat2"]
            lon2 = arguments["lon2"]
            
            result = get_distance_between(lat1, lon1, lat2, lon2)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "identify_maritime_region":
            lat = arguments["latitude"]
            lon = arguments["longitude"]
            region = identify_maritime_region(lat, lon)
            
            result = {"region": region} if region else {"region": "Unknown"}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "find_nearest_port":
            lat = arguments["latitude"]
            lon = arguments["longitude"]
            port_name, distance = find_nearest_port(lat, lon)
            
            result = {
                "port_name": port_name,
                "distance_nm": distance,
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "find_nearest_waterway":
            lat = arguments["latitude"]
            lon = arguments["longitude"]
            waterway_name, distance = find_nearest_waterway(lat, lon)
            
            result = {
                "waterway_name": waterway_name,
                "distance_nm": distance,
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "calculate_fleet_position":
            fleet_name = arguments["fleet_name"]
            lat, lon = calculate_fleet_position(fleet_name)
            
            result = {
                "fleet_name": fleet_name,
                "fleet_position": {
                    "latitude": lat,
                    "longitude": lon,
                }
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "is_ship_in_fleet":
            mmsi = arguments["mmsi"]
            result_str = is_ship_in_fleet(mmsi)
            return [types.TextContent(type="text", text=result_str)]
        
        elif name == "get_vessel_destination":
            mmsi = arguments["mmsi"]
            num_detections = arguments.get("number_detections", 300)
            
            try:
                calculate_vector_and_distance_sum(mmsi, num_detections)
                # This function prints output; wrap in try-except to handle
                result = {
                    "mmsi": mmsi,
                    "note": "Destination analysis completed. See server logs for trajectory analysis."
                }
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error analyzing destination: {str(e)}")]
        
        else:
            return [types.ErrorContent(type="error", error=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [types.ErrorContent(type="error", error=f"Tool execution error: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with server:
        opts = InitializationOptions(server_params={})
        await server.initialize(opts)
        print("AIS Vessel Intelligence MCP Server running...")
        print("Available tools:")
        for tool in await handle_list_tools():
            print(f"  - {tool.name}: {tool.description}")
        
        await server.wait_for_shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
