import socketio
import uvicorn
from actint.tests.mcp.host import run_agent
from actint.web_sockets.data_retrieval import get_positions_before_time, get_positions_after_time, create_json_packet
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
import sys
from actint.mcp.agent_query_from_chat import process_chat_message

from actint.web_sockets.defaults import sio, app



# Simulation Updater

messages = {}

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)


# @sio.on("simulation_init")
# async def handle_simulation_init(sid, data):
#     print(f"Simulation init from {sid}: {data}", file=sys.stderr)
    
#     start_time = str(data["start_time"]+":07.000000")
#     # Send to EVERYONE else
#     await sio.emit("private_response", {"msg": f"Sending simulation data up to {data["start_time"]}"}, to=sid)

#     (MMSIs, results) = get_positions_before_time(start_time)

#     await sio.emit("previous_data", {"MMSIs": MMSIs, "results": results}, to=sid)
#     await sio.emit("private_response", {"msg": f"Finished sending simulation data up to {data["start_time"]}"}, to=sid)

#     future_detections = get_positions_after_time(start_time)
#     await send_simulation_updates(sid, future_detections, start_time)



# async def send_simulation_updates(sid, data, start_time):
#     current_time = start_time
#     for detection in data:
#         time_between = datetime.strptime(detection[2], '%Y-%m-%dT%H:%M:%S.%f') - datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S.%f')
#         if(time_between.total_seconds() > 0):
#             await asyncio.sleep(time_between.total_seconds())
#         json_packet = create_json_packet(detection) 
#         await sio.emit("new_detection", json_packet, to=sid)
#         current_time = detection[2]










# Chat manager

# from actint.web_sockets.web_socket import sio, app
import random
import socketio
import asyncio

from actint.web_sockets.map_functioons import set_map_position, draw_rectangle, draw_circle, draw_line

messages = {}

@sio.on("recieve_message")
async def handle_recieve_message(sid, data):
    print(f"Message from {sid}: {data}")
    
    draw_rectangle(sid, lat1=37.7749, lon1=122.4194, lat2=-37.7849, lon2=-122.4094, color="green") # Example: Draw a rectangle in San Francisco
    draw_circle(sid, radius=5000, center_lat=37.7749, center_lon=-122.4194, color="red") # Example: Draw a circle around San Francisco
    draw_line(sid, points=[(37.7749, -122.4194), (37.7849, 122.4094)], color="blue") # Example: Draw a line in San Francisco
    set_map_position(37.7749, -122.4194, 10) # Example: Set map to San Francisco with zoom level 10
    # Extract the user's string message
    user_text = data.get("message", "")

    
    # Offload the synchronous smolagents run to a background thread
    try:
        agent_response_text = await asyncio.to_thread(process_chat_message, sid, user_text)
    except Exception as e:
        agent_response_text = f"Error processing message: {str(e)}"

    # Package the LLM response into the structure React expects
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
    if messages.get(sid):
        del messages[sid]

if __name__ == "__main__":
    # "0.0.0.0" means "listen on all network interfaces" 
    # (so other computers can connect to your IP)
    uvicorn.run(app, host="0.0.0.0", port=3050)