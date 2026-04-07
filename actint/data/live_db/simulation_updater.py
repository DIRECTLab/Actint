import socketio
import uvicorn
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
from web_socket import sio, app


messages = {}

# 2. Handle Connection (Automatic ID assigned)
@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!")

# 3. Handle a CUSTOM event (No if/else needed!)

from data_retrieval import get_positions_before_time, get_positions_after_time, create_json_packet

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
    await sio.emit("send_response", newMessage, to=sid)
    

    # Generate random values
    # uniform(a, b) gives a random float between two numbers
    random_lat = random.uniform(-90.0, 90.0)
    random_lon = random.uniform(-180.0, 180.0)

    # randint(a, b) gives a random integer (good for zoom levels)
    random_zoom = random.randint(3, 10) 

    # Emit the message
    set_map_position(sid, random_lat, random_lon, random_zoom)


def set_map_position(sid, lat, lon, zoom):
    # This function can be called to set the map position for a specific client
    asyncio.create_task(sio.emit("set_map_position", {
        "lat": lat, 
        "lon": lon, 
        "zoom": zoom
    }, to=sid))

# 4. Handle Disconnect
@sio.event
async def disconnect(sid):
    print(f"User {sid} left.")
    if messages.get(sid):
        del messages[sid]
        














# ... all your existing code here ...

if __name__ == "__main__":
    # "0.0.0.0" means "listen on all network interfaces" 
    # (so other computers can connect to your IP)
    uvicorn.run(app, host="0.0.0.0", port=2500)





















# Different functions that the server will need to have: 
# Flow of data:

# 1. The client establishes a connection to the server, server adds client to a list of connected clients. 
# 2. Once connected, sends over information about the state of the simulation (e.g. simulation time, simulation speed)
# 3. The server accepts the data from the client and begins sending over needed data for the simulation until the start state. 
# 4. The server sends a final piece of information letting the computer know that it is done and the start time of the simulation.
# 5. The server will send new information over to the computer about simulation updates. 
# 6. The server will also listen for any queries that may be sent to it from that computer.

# 7. Once the server has finished sending over everything for the simulation, it will close the client's connection and delete it from its list of connected

# Needed functions:

# For server: 
# 1. Function that jsonifies messages from the client and sends information to the correct functions
# 2. Function that will add a new client and assign a client number if that has not yet been done
# 3. Function that takes the information about the simulation and will send everything over (with packet indicating start of sim)
# 4. Function that listens for queries by the user
# 5. Function that responds to queries from the user
# 6. Function that waits for things in the sim to happen and sends stuff over when it is time
# 7. Potential function that closes the connection and does some cleanup


# For client:
# 1. Function that asks to connect to the server and stores the client's identification
# 2. Function that sends the server information about the simulation
# 3. Function which queries the server
# 4. Function which accept the server's response and displays it.
# 5. Function which recieves and manages incoming information about the simulation.