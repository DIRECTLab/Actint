# backend/ui_tools/map_edit_tools.py
import asyncio
import json
from smolagents import Tool
from backend.event_loop_registry import get_event_loop
from backend.transport.server_sent_events.map_events import (
    set_map_position,
    draw_rectangle,
    draw_circle,
    draw_line,
    add_marker
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
        "popup_msg": {"type": "string", "description": "Optional message to show in a popup over the marker. Pass an empty string (\"\") to show no popup."},
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat, lon, popup_msg) -> str:
        lat = float(lat)
        lon = float(lon)
        future = asyncio.run_coroutine_threadsafe(
            add_marker(self.sid, lat=lat, lon=lon, popup_msg=popup_msg),
            get_event_loop(),
        )
        future.result()
        return (f"Marker added with latitude {lat} and longitude {lon}")



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