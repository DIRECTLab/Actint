import socketio
import uvicorn
from actint.web_sockets.data_retrieval import get_positions_before_time, get_positions_after_time, create_json_packet
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
import sys
import random
import socketio
import asyncio

from actint.web_sockets.map_functions import set_map_position, draw_rectangle, draw_circle, draw_line
from actint.mcp.chat_start import remove_user_agent, user_agent_query
from actint.web_sockets.defaults import sio, app



# Simulation Updater

messages = {}

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)


@sio.on("simulation_init")
async def handle_simulation_init(sid, data):
    print(f"Simulation init from {sid}: {data}", file=sys.stderr)
    
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

# from actint.web_sockets.web_socket import sio, app


@sio.on("recieve_message")
async def query_agent(sid, data):
    print(f"Message from {sid}: {data}", file=sys.stderr)
    
    # draw_rectangle(sid, lat1=37.7749, lon1=122.4194, lat2=-37.7849, lon2=-122.4094, color="green") # Example: Draw a rectangle in San Francisco
    # draw_circle(sid, radius=5000, center_lat=37.7749, center_lon=-122.4194, color="red") # Example: Draw a circle around San Francisco
    # draw_line(sid, points=[(37.7749, -122.4194), (37.7849, 122.4094)], color="blue") # Example: Draw a line in San Francisco
    # await set_map_position(37.7749, -122.4194, 6, sid=420) # Example: Set map to San Francisco with zoom level 10
    # Extract the user's string message
    user_text = data.get("message", "")

    
    # Offload the synchronous smolagents run to a background thread
    

    agent_response_text = await user_agent_query(user_text, sid)

    if agent_response_text is None:
        agent_response_text = "Agent failed to respond."


    newMessage = {
        "message": agent_response_text,
        "sentTime": datetime.now().strftime("%H:%M:%S"), # Dynamic time
        "sender": 'ChatBot',
        "direction": 'incoming',
        "position": 'single',
    }
    
    # Send the response back to the specific client
    await sio.emit("send_response", newMessage, to=sid)





        


@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    remove_user_agent(sid)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3050)