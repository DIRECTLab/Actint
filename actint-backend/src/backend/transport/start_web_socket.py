from backend.agent.agent import remove_agent_session, query_agent
import uvicorn
from backend.config import config
from backend.transport.connection import sio, app
import sys


@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)

@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    remove_agent_session(sid)

import backend.transport.chat_events
# import backend.transport.simulation_events


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WEB_SOCKET_PORT)