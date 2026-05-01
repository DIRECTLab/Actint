import asyncio
from smolagents import Tool
from actint.web_sockets.map_functions import set_map_position, draw_rectangle, draw_circle, draw_line


class ZoomTool(Tool):
    name = "position_map"
    description = "Positions the map to a certain lat, lon, and zoom."
    inputs = {
        "lat": {"type": "number", "description": "Latitude"},
        "lon": {"type": "number", "description": "Longitude"},
        "zoom": {"type": "integer", "description": "Zoom level"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat: float, lon: float, zoom: int) -> str:
        asyncio.create_task(set_map_position(lat, lon, zoom, sid=self.sid))
        return f"Map positioned to lat: {lat}, lon: {lon}, zoom: {zoom}, sid is {self.sid}"


class DrawRectangleTool(Tool):
    name = "draw_rectangle"
    description = "Draws a rectangle on the map given two lat/lon points and a color."
    inputs = {
        "lat1": {"type": "number", "description": "Latitude of first corner"},
        "lon1": {"type": "number", "description": "Longitude of first corner"},
        "lat2": {"type": "number", "description": "Latitude of opposite corner"},
        "lon2": {"type": "number", "description": "Longitude of opposite corner"},
        "color": {"type": "string", "description": "Color of the rectangle"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat1: float, lon1: float, lat2: float, lon2: float, color: str) -> str:
        asyncio.create_task(draw_rectangle(self.sid, lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2, color=color))
        return f"Rectangle drawn with corners ({lat1}, {lon1}) and ({lat2}, {lon2}) in color {color} for sid {self.sid}"
    

class DrawCircleTool(Tool):
    name = "draw_circle"
    description = "Draws a circle on the map given a center point, radius, and color."
    inputs = {
        "center_lat": {"type": "number", "description": "Latitude of the center"},
        "center_lon": {"type": "number", "description": "Longitude of the center"},
        "radius": {"type": "number", "description": "Radius of the circle in meters"},
        "color": {"type": "string", "description": "Color of the circle"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, center_lat: float, center_lon: float, radius: float, color: str) -> str:
        asyncio.create_task(draw_circle(self.sid, radius=radius, center_lat=center_lat, center_lon=center_lon, color=color))
        return f"Circle drawn with center ({center_lat}, {center_lon}), radius {radius}m in color {color} for sid {self.sid}"
    
class DrawLineTool(Tool):
    name = "draw_line"
    description = "Draws a line on the map given a list of lat/lon points and a color."
    inputs = {
        "points": {"type": "array", "description": "List of (lat, lon) tuples defining the line"},
        "color": {"type": "string", "description": "Color of the line"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, points: list, color: str) -> str:
        asyncio.create_task(draw_line(self.sid, points=points, color=color))
        return f"Line drawn with points {points} in color {color} for sid {self.sid}"