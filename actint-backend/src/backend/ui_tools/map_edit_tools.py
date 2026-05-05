import asyncio
from smolagents import Tool
from backend.transport.server_sent_events.map_events import set_map_position, draw_rectangle, draw_circle, draw_line


class ZoomTool(Tool):
    name = "position_map"
    description = "Positions the map to a certain lat, lon, and zoom."
    inputs = {
        "lat": {"type": "string", "description": "Latitude"},
        "lon": {"type": "string", "description": "Longitude"},
        "zoom": {"type": "string", "description": "Zoom level"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat: float | int | str, lon: float | int | str, zoom: int | str) -> str:
        lat = float(lat)
        lon = float(lon)
        zoom = int(zoom)
        asyncio.create_task(set_map_position(lat, lon, zoom, sid=self.sid))
        return f"Map positioned to lat: {lat}, lon: {lon}, zoom: {zoom}, sid is {self.sid}"


class DrawRectangleTool(Tool):
    name = "draw_rectangle"
    description = "Draws a rectangle on the map given two lat/lon points and a color."
    inputs = {
        "lat1": {"type": "string", "description": "Latitude of first corner"},
        "lon1": {"type": "string", "description": "Longitude of first corner"},
        "lat2": {"type": "string", "description": "Latitude of opposite corner"},
        "lon2": {"type": "string", "description": "Longitude of opposite corner"},
        "color": {"type": "string", "description": "Color of the rectangle"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, lat1: float | int | str, lon1: float | int | str, lat2: float | int | str, lon2: float | int | str, color: str) -> str:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
        asyncio.create_task(draw_rectangle(self.sid, lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2, color=color))
        return f"Rectangle drawn with corners ({lat1}, {lon1}) and ({lat2}, {lon2}) in color {color} for sid {self.sid}"
    

class DrawCircleTool(Tool):
    name = "draw_circle"
    description = "Draws a circle on the map given a center point, radius, and color."
    inputs = {
        "center_lat": {"type": "string", "description": "Latitude of the center"},
        "center_lon": {"type": "string", "description": "Longitude of the center"},
        "radius": {"type": "string", "description": "Radius of the circle in meters"},
        "color": {"type": "string", "description": "Color of the circle"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, center_lat: float | int | str, center_lon: float | int | str, radius: float | int | str, color: str) -> str:
        center_lat = float(center_lat)
        center_lon = float(center_lon)
        radius = float(radius)
        asyncio.create_task(draw_circle(self.sid, radius=radius, center_lat=center_lat, center_lon=center_lon, color=color))
        return f"Circle drawn with center ({center_lat}, {center_lon}), radius {radius}m in color {color} for sid {self.sid}"
    
class DrawLineTool(Tool):
    name = "draw_line"
    description = "Draws a line on the map given a list of lat/lon points and a color."
    inputs = {
        "points": {"type": "string", "description": "List of (lat, lon) tuples defining the line"},
        "color": {"type": "string", "description": "Color of the line"}
    }
    output_type = "string"

    def __init__(self, sid, sio_instance, **kwargs):
        super().__init__(**kwargs)
        self.sid = sid
        self.sio = sio_instance

    def forward(self, points: list | str, color: str) -> str:
        if isinstance(points, str):
            import json
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


class GetMapInfoTool(Tool):
    name = "get_map_info"
    description = "Gets information about things on the map"
    inputs = {}
    output_type = "string"

    def __init__(self, sid, sio_instance):
        super().__init__()
        self.sid = sid
        self.sio = sio_instance

    def forward(self) -> str: 

        future = asyncio.run_coroutine_threadsafe(
            get_map_info(self.sid), get_event_loop()
        )
        result = future.result()
        return result
