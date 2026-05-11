import uvicorn
import sys
import asyncio
from datetime import datetime

from backend.agent.agent import create_agent, query_agent_instance
from backend.ui_tools.map_edit_tools import ZoomTool, DrawCircleTool, DrawLineTool, DrawRectangleTool
from backend.transport.connection import sio, app
from backend.config import config
from backend.event_loop_registry import set_event_loop

user_agents = {}

@sio.event
async def connect(sid, environ):
    set_event_loop(asyncio.get_event_loop())
    print(f"User {sid} connected! New user.", file=sys.stderr)


# ==================================================
# Chat Manager
# ==================================================

@sio.on("recieve_message")
async def handle_agent_query(sid, data):
    user_text = data.get("message", "")

    if sid not in user_agents:
        print(f"Creating new agent for new user {sid}.", file=sys.stderr)
        ui_tools = [
            ZoomTool(sid, sio),
            DrawRectangleTool(sid, sio),
            DrawCircleTool(sid, sio),
            DrawLineTool(sid, sio),
        ]
        user_agents[sid] = create_agent(additional_tools=ui_tools)
    else:
        print(f"Using existing agent for returning user {sid}.", file=sys.stderr)

    agent_response_text = await query_agent_instance(
        user_agents[sid], user_text
    )

    new_msg = {
        "message": agent_response_text or "Agent failed to respond.",
        "sentTime": datetime.now().strftime("%H:%M:%S"),
        "sender": "ChatBot",
        "direction": "incoming",
        "position": "single",
    }

    await sio.emit("send_response", new_msg, to=sid)


@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    if sid in user_agents:
        del user_agents[sid]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)