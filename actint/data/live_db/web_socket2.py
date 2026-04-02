import socketio

# 1. Initialize the server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)

# 2. Handle Connection (Automatic ID assigned)
@sio.event
async def connect(sid, environ):
    print(f"User {sid} connected!")

# 3. Handle a CUSTOM event (No if/else needed!)
@sio.on("chat_message")
async def handle_chat(sid, data):
    print(f"Message from {sid}: {data}")
    # Send to EVERYONE else
    await sio.emit("private_response", {"msg": "Hello world"}, to=sid)

# 4. Handle Disconnect
@sio.event
async def disconnect(sid):
    print(f"User {sid} left.")