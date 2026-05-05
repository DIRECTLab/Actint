import asyncio
from backend.transport.start_web_socket import sio


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



async def draw_rectangle(sid, lat1, lon1, lat2, lon2, color="blue"):
    await sio.emit("draw_rectangle", {
        "lat1": lat1,
        "lon1": lon1,
        "lat2": lat2,
        "lon2": lon2,
        "color": color,
    }, to=sid) #This will need to have to=sid added back later after the tool can be accessed by the LLM


async def draw_circle(sid, radius, center_lat, center_lon, color="blue"):
    await sio.emit("draw_circle", {
        "radius": radius,
        "lat": center_lat,
        "lon": center_lon,
        "color": color,
    }, to=sid) #This will need to have to=sid added back later after the tool can be accessed by the LLM


async def draw_line(sid, points,  color="blue"):
    await sio.emit("draw_line", {
        "points": points,
        "color": color,
    }, to=sid) #This will need to have to=sid added back later after the tool can be accessed by the LLM