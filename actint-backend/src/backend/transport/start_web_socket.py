import socketio
import sys
from backend.agent.agent import remove_user_agent, user_agent_query
import uvicorn

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)



@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!", file=sys.stderr)





@sio.event
async def disconnect(sid):
    print(f"User {sid} left.", file=sys.stderr)
    remove_user_agent(sid)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3050)