from datetime import datetime
import asyncio

from backend.agent.agent import create_agent, query_agent_instance
import uvicorn
from backend.config import config
from backend.ui_tools.map_edit_tools import ZoomTool, AddMarkerTool, DrawVesselTrajectoryTool, DrawRectangleTool, DrawCircleTool, DrawLineTool, DrawPolygonTool, DeleteObjectTool
from backend.transport.connection import sio, app
import sys

connections = {}

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)
    connections[sid] = {"agent": None}

    new_user = connections[sid]

    if new_user["agent"] is None:
        print(f"\033[1;33mCreating new agent for new user {sid}.\033[0m", file=sys.stderr)
        ui_tools = [
            ZoomTool(sid, sio),
            AddMarkerTool(sid, sio),
            DrawVesselTrajectoryTool(sid, sio),
            DrawRectangleTool(sid, sio),
            DrawCircleTool(sid, sio),
            DrawLineTool(sid, sio),
            DrawPolygonTool(sid, sio),
            DeleteObjectTool(sid, sio),
        ]
        new_user["agent"] = create_agent(additional_tools=ui_tools)


@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    if sid in connections:
        del connections[sid]

@sio.on("chat_message")
async def handle_agent_query(sid, data):
    user_text = data.get("message", "")
    user_agent = connections[sid]["agent"]
    agent_response_text = "Something went wrong and the agent did not respond."
    
    if not user_text.strip() == "":
        agent_response_text = await query_agent_instance(
            user_agent, user_text, make_get_map_info(sio, sid)
        )
        #might want get_map_info right here
    else:
        agent_response_text = "Received empty message, please send a valid query."

    new_msg = {
        "message": agent_response_text or "Agent failed to respond.",
        "sentTime": datetime.now().strftime("%H:%M:%S"),
        "sender": "ChatBot",
        "direction": "incoming",
        "position": "single",
    }

    await sio.emit("send_response", new_msg, to=sid)


def make_get_map_info(sio, sid):
    async def get_map_info():
        map_info = await sio.call("get_map_information", {}, to=sid, timeout=8)
        if map_info:
            return map_info
        else:
            raise TimeoutError("Failed to fetch the map information in time")
    return get_map_info
    
    



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)