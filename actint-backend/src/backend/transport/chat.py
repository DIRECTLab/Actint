import uvicorn
from datetime import datetime
import sys

from backend.agent.agent import user_agent_query, remove_user_agent
from backend.transport.server_sent_events.map_events import set_map_position, draw_rectangle, draw_circle, draw_line

from backend.transport.start_web_socket import sio, app



# Simulation Updater

messages = {}





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