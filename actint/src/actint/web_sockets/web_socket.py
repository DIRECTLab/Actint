import socketio
import uvicorn
from actint.tests.mcp.host import run_agent
from actint.web_sockets.data_retrieval import get_positions_before_time, get_positions_after_time, create_json_packet
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
from actint.mcp.agent_query_from_chat import run_agent

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)



# Simulation Updater

messages = {}

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!")


@sio.on("simulation_init")
async def handle_simulation_init(sid, data):
    print(f"Simulation init from {sid}: {data}")
          
    start_time = str(data["start_time"]+":07.000000")
    # Send to EVERYONE else
    await sio.emit("private_response", {"msg": f"Sending simulation data up to {data["start_time"]}"}, to=sid)

    (MMSIs, results) = get_positions_before_time(start_time)

    await sio.emit("previous_data", {"MMSIs": MMSIs, "results": results}, to=sid)
    await sio.emit("private_response", {"msg": f"Finished sending simulation data up to {data["start_time"]}"}, to=sid)

    future_detections = get_positions_after_time(start_time)
    await send_simulation_updates(sid, future_detections, start_time)



async def send_simulation_updates(sid, data, start_time):
    current_time = start_time
    for detection in data:
        time_between = datetime.strptime(detection[2], '%Y-%m-%dT%H:%M:%S.%f') - datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S.%f')
        if(time_between.total_seconds() > 0):
            await asyncio.sleep(time_between.total_seconds())
        json_packet = create_json_packet(detection) 
        await sio.emit("new_detection", json_packet, to=sid)
        current_time = detection[2]










# Chat manager

from actint.web_sockets.web_socket import sio, app
import random
import socketio
import asyncio

messages = {}
#Handle recieving a message
@sio.on("recieve_message")
async def handle_recieve_message(sid, data):
    print(f"Message from {sid}: {data}")
    if(messages.get(sid) == None):
        messages[sid] = []
    messages[sid].append(data)
    newMessage = {
        "message": "recieved the message, you will never get any AI response",
        "sentTime": 'just now',
        "sender": 'ChatBot',
        "direction": 'incoming',
        "position": 'single',
    }
    print(newMessage)
    
    run_agent("change my latitude and longitude to 0 0 with zoom level 12") 


def set_map_position(sid, lat, lon, zoom):
    # This function can be called to set the map position for a specific client
    asyncio.create_task(sio.emit("set_map_position", {
        "lat": lat, 
        "lon": lon, 
        "zoom": zoom
    })) #This will need to have to=sid added back later after the tool can be accessed by the LLM

    


        



@sio.event
async def disconnect(sid):
    print(f"User {sid} left.")
    if messages.get(sid):
        del messages[sid]

if __name__ == "__main__":
    # "0.0.0.0" means "listen on all network interfaces" 
    # (so other computers can connect to your IP)
    uvicorn.run(app, host="0.0.0.0", port=2500)