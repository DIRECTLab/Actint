import uvicorn
import sys
import os
from datetime import datetime

from backend.agent.agent import remove_agent_session, query_agent
from backend.ui_tools.map_edit_tools import ZoomTool, DrawCircleTool, DrawLineTool, DrawRectangleTool
from backend.transport.defaults import sio, app
from backend.config import config

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)

# ==================================================
# Chat Manager
# ==================================================

@sio.on("recieve_message")
async def handle_agent_query(sid, data):
    user_text = data.get("message", "")
    
    # Define transport-specific tools tied to this UI session
    ui_tools = [
        ZoomTool(sid, sio), 
        DrawRectangleTool(sid, sio), 
        DrawCircleTool(sid, sio), 
        DrawLineTool(sid, sio)
    ]
    
    # Pass them into the generic query function
    agent_response_text = await query_agent(user_text, session_id=sid, additional_tools=ui_tools)
    
    new_msg = {
        "message": agent_response_text,
        "sentTime": datetime.now().strftime("%H:%M:%S"), # Dynamic time
        "sender": 'ChatBot',
        "direction": 'incoming',
        "position": 'single',
    }

    # Send the response back to the specific client
    await sio.emit("send_response", new_msg, to=sid)


@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    remove_agent_session(sid)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)