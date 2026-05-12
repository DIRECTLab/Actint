from datetime import datetime

from backend.agent.agent import create_agent, query_agent_instance
import uvicorn
from backend.config import config
from backend.transport.connection import sio, app
import sys

connections = {}

@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)
    connections[sid] = {"agent": None}

    new_user = connections[sid]

    if new_user["agent"] is None:
        print(f"Creating new agent for new user {sid}.", file=sys.stderr)
        new_user["agent"] = create_agent()


@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    if sid in connections:
        del connections[sid]

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

@sio.on("get_heatmap")
async def handle_get_heatmap(sid, data):
    from backend.data_processing.heatmap import fetch_heatmap

    try:
        points, max_val = fetch_heatmap()

        await sio.emit(
            "set_heatmap",
            {
                "points": points,
                "max": max_val,
            },
            to=sid
        )

    except Exception as e:
        print(e)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)