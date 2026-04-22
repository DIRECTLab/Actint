import asyncio
from actint.web_sockets.defaults import sio, app
import uvicorn


def set_map_position(lat, lon, zoom):
    # This function can be called to set the map position for a specific client
    asyncio.create_task(sio.emit("set_map_position", {
        "lat": lat, 
        "lon": lon, 
        "zoom": zoom
    })) #This will need to have to=sid added back later after the tool can be accessed by the LLM


def set_map_position(lat, lon, zoom):
    # This function can be called to set the map position for a specific client
    asyncio.create_task(sio.emit("set_map_position", {
        "lat": lat, 
        "lon": lon, 
        "zoom": zoom
    })) #This will need to have to=sid added back later after the tool can be accessed by the LLM



def draw_rectangle(sid, lat1, lon1, lat2, lon2, color="blue"):
    asyncio.create_task(sio.emit("draw_rectangle", {
        "lat1": lat1,
        "lon1": lon1,
        "lat2": lat2,
        "lon2": lon2,
        "color": color,
    }, to=sid)) #This will need to have to=sid added back later after the tool can be accessed by the LLM


def draw_circle(sid, radius, center_lat, center_lon, color="blue"):
    asyncio.create_task(sio.emit("draw_circle", {
        "radius": radius,
        "lat": center_lat,
        "lon": center_lon,
        "color": color,
    }, to=sid)) #This will need to have to=sid added back later after the tool can be accessed by the LLM



def draw_line(sid, points,  color="blue"):
    asyncio.create_task(sio.emit("draw_line", {
        "points": points,
        "color": color,
    }, to=sid)) #This will need to have to=sid added back later after the tool can be accessed by the LLM