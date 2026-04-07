from web_socket import sio, app
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
        
