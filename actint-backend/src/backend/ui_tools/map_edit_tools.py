# backend/ui_tools/map_edit_tools.py
import asyncio
import json
from smolagents import Tool
from backend.event_loop_registry import get_event_loop
from backend.transport.server_sent_events.map_events import (
    set_map_position,
    add_marker,
    draw_vessel_trajectory,
    draw_rectangle,
    draw_circle,
    draw_line,
    draw_polygon,
    delete_object,
    get_map_info,
)


class ZoomTool(Tool):
    name = "position_map"
    description = "Positions the map to a certain lat, lon, and zoom."
    inputs = {
        "lat": {"type": "string", "description": "Latitude"},
        "lon": {"type": "string", "description": "Longitude"},
        "zoom": {"type": "string", "description": "Zoom level"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat, lon, zoom) -> str:
        lat, lon, zoom = float(lat), float(lon), int(zoom)
        future = asyncio.run_coroutine_threadsafe(
            set_map_position(lat, lon, zoom, sid=self.sid), get_event_loop()
        )
        future.result()
        return f"Map positioned to lat: {lat}, lon: {lon}, zoom: {zoom}"
    

class AddMarkerTool(Tool):
    name="add_marker"
    description = "Adds a marker a specific latitude and longitue"
    inputs = {
        "lat": {"type": "string", "description": "Latitude of marker"},
        "lon": {"type": "string", "description": "Longitude of marker"},
        "popup_description": {"type": "string", "description": "description for what the new marker is"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat, lon, popup_description) -> str:
        lat = float(lat)
        lon = float(lon)
        future = asyncio.run_coroutine_threadsafe(
            add_marker(self.sid, lat=lat, lon=lon, popup_description=popup_description),
            get_event_loop(),
        )
        future.result()
        return (f"Marker added with latitude {lat} and longitude {lon}")


class DrawVesselTrajectoryTool(Tool):
    name = "draw_vessel_trajectory"
    description = "Draws the trajectory of a vessel given its position and direction. Draws a specified number of nautical miles out."
    inputs = {
        "lat": {"type": "string", "description": "Latitude of marker"},
        "lon": {"type": "string", "description": "Longitude of marker"},
        "degree": {"type": "string", "description": "Degree of vessel course"},
        "distance_nm": {"type": "string", "description": "How far to draw the vessel trajectory in nautical miles"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat, lon, degree, distance_nm) -> str:
        lat= float(lat)
        lon = float(lon)
        future = asyncio.run_coroutine_threadsafe(
            draw_vessel_trajectory(
                self.sid, lat=lat, lon=lon, degree=degree, distance_nm=distance_nm,
            ),
            get_event_loop(),
        )
        future.result()
        return (f"Trajectory added to map with position Lat: {lat}, Lon: {lon}, with course {degree} and distance {distance_nm}")

class DrawRectangleTool(Tool):
    name = "draw_rectangle"
    description = "Draws a rectangle on the map given two lat/lon points and a color."
    inputs = {
        "lat1": {"type": "string", "description": "Latitude of first corner"},
        "lon1": {"type": "string", "description": "Longitude of first corner"},
        "lat2": {"type": "string", "description": "Latitude of opposite corner"},
        "lon2": {"type": "string", "description": "Longitude of opposite corner"},
        "color": {"type": "string", "description": "Color of the rectangle"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat1, lon1, lat2, lon2, color) -> str:
        lat1, lon1 = float(lat1), float(lon1)
        lat2, lon2 = float(lat2), float(lon2)
        future = asyncio.run_coroutine_threadsafe(
            draw_rectangle(
                self.sid, lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2, color=color
            ),
            get_event_loop(),
        )
        future.result()
        return (
            f"Rectangle drawn with corners ({lat1}, {lon1}) "
            f"and ({lat2}, {lon2}) in {color}"
        )


class DrawCircleTool(Tool):
    name = "draw_circle"
    description = "Draws a circle on the map given a center point, radius, and color."
    inputs = {
        "center_lat": {"type": "string", "description": "Latitude of the center"},
        "center_lon": {"type": "string", "description": "Longitude of the center"},
        "radius": {"type": "string", "description": "Radius of the circle in meters"},
        "color": {"type": "string", "description": "Color of the circle"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, center_lat, center_lon, radius, color) -> str:
        center_lat, center_lon = float(center_lat), float(center_lon)
        radius = float(radius)
        future = asyncio.run_coroutine_threadsafe(
            draw_circle(
                self.sid,
                radius=radius,
                center_lat=center_lat,
                center_lon=center_lon,
                color=color,
            ),
            get_event_loop(),
        )
        future.result()
        return (
            f"Circle drawn at ({center_lat}, {center_lon}), "
            f"radius {radius}m in {color}"
        )


class DrawLineTool(Tool):
    name = "draw_line"
    description = "Draws a line on the map given a list of lat/lon points and a color."
    inputs = {
        "points": {
            "type": "string",
            "description": "List of (lat, lon) tuples defining the line",
        },
        "color": {"type": "string", "description": "Color of the line"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, points, color) -> str:
        if isinstance(points, str):
            points = json.loads(points)
        future = asyncio.run_coroutine_threadsafe(
            draw_line(self.sid, points=points, color=color), get_event_loop()
        )
        future.result()
        return f"Line drawn with points {points} in {color}"


class DrawPolygonTool(Tool):
    name = "draw_polygon"
    description = "Draws a polygon on the map given a list of lat/lon points and a color."
    inputs = {
        "points": {
            "type": "string",
            "description": "List of (lat, lon) tuples defining the polygon",
        },
        "color": {"type": "string", "description": "Color of the polygon"},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, points, color) -> str:
        if isinstance(points, str):
            points = json.loads(points)
        future = asyncio.run_coroutine_threadsafe(
            draw_polygon(self.sid, points=points, color=color), get_event_loop()
        )
        future.result()
        return f"Polygon drawn with points {points} in {color}"


class DeleteObjectTool(Tool):
    name = "delete_object"
    description = "Deletes objects drawn on the map"
    inputs = {
        "object_number": {
            "type": "string",
            "description": "the identifier of the object that needs deletion",
        }
    }
    output_type = "string"
    
    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, object_number) -> str:
        
        future = asyncio.run_coroutine_threadsafe(
            delete_object(self.sid, object_number=object_number), get_event_loop()
        )
        future.result()
        return f"Deleted object {object_number} from the map objects"


class GetMapInfoToool(Tool):
    name = "get_map_info"
    description = "Gets information about things on the map"
    inputs = None
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self) -> str: 

        future = asyncio.run_coroutine_threadsafe(
            get_map_info(self.sid), get_event_loop()
        )
        result = future.result()
        return result