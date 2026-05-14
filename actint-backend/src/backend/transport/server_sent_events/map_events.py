import asyncio
from backend.transport.connection import sio


async def set_map_position(lat, lon, zoom, sid=None):
    # This function can be called to set the map position for a specific client.
    payload = {
        "lat": lat,
        "lon": lon,
        "zoom": zoom,
    }
    if sid:
        asyncio.create_task(sio.emit("set_map_position", payload, to=sid))
    else:
        asyncio.create_task(sio.emit("set_map_position", payload)) # May be good to comment this out if there are multiple users for real



async def add_marker(sid, lat, lon, popup_description):
    await sio.emit("add_marker", {
        "lat": lat,
        "lon": lon,
        "popup": popup_description
    }, to=sid)

async def draw_vessel_trajectory(sid, lat, lon, degree, distance_nm, color="blue"): #I need to add the ability for the AI to choose a color
    await sio.emit("draw_vessel_trajectory", {
        "lat": lat,
        "lon": lon,
        "degree": degree,
        "distance_nm": distance_nm,
    }, to=sid)

async def draw_rectangle(sid, lat1, lon1, lat2, lon2, color="blue"):
    await sio.emit("draw_rectangle", {
        "lat1": lat1,
        "lon1": lon1,
        "lat2": lat2,
        "lon2": lon2,
        "color": color,
    }, to=sid) 

async def draw_circle(sid, radius, center_lat, center_lon, color="blue"):
    await sio.emit("draw_circle", {
        "radius": radius,
        "lat": center_lat,
        "lon": center_lon,
        "color": color,
    }, to=sid) 

async def draw_line(sid, points,  color="blue"):
    await sio.emit("draw_line", {
        "points": points,
        "color": color,
    }, to=sid)

async def draw_polygon(sid, points, color="blue"):
    await sio.emit("draw_polygon", {
        "points": points,
        "color": color
    }, to=sid)

async def delete_object(sid, object_number):
    await sio.emit("delete_object", {
        "object_number": object_number
    }, to=sid)
