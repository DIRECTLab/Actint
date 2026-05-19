from datetime import datetime
from backend.agent.agent import create_agent, query_agent_instance
import uvicorn
from backend.config import config
from backend.ui_tools.map_edit_tools import ZoomTool, DrawRectangleTool, DrawCircleTool, DrawLineTool, AddMarkerTool
from backend.transport.connection import sio, app
import sys
import gc

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
            DrawRectangleTool(sid, sio),
            DrawCircleTool(sid, sio),
            DrawLineTool(sid, sio),
            AddMarkerTool(sid, sio)
        ]
        new_user["agent"] = create_agent(model=getattr(app, 'model', None), additional_tools=ui_tools)



@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    if sid in connections:
        agent = connections[sid].get("agent")
        if agent and hasattr(agent, "memory"):
            agent.memory.steps.clear()
        
        del connections[sid]
        
        # Force garbage collection to free memory
        gc.collect()
        
        # If using PyTorch, empty the CUDA cache to release GPU memory
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

@sio.on("recieve_message")
async def handle_agent_query(sid, data):
    user_text = data.get("message", "")
    user_agent = connections[sid]["agent"]
    agent_response_text = "Something went wrong and the agent did not respond."

    if not user_text.strip() == "":
        agent_response_text = await query_agent_instance(
            user_agent, user_text
        )
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

if __name__ == "__main__":
    from backend.agent.agent import init_model
    app.model = init_model()
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)