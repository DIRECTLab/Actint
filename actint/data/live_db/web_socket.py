import socketio
import uvicorn

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)


if __name__ == "__main__":
    # "0.0.0.0" means "listen on all network interfaces" 
    # (so other computers can connect to your IP)
    uvicorn.run(app, host="0.0.0.0", port=2500)