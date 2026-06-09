import argparse
import asyncio
import json
import sys
from datetime import datetime
from uuid import uuid4

try:
    import readline  # noqa: F401 -- enables up-arrow input history automatically
except ImportError:
    # readline is Unix/macOS only. Install pyreadline3 on Windows.
    pass

try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False


SESSION_ID = uuid4().hex[:8]

chat_history: list[dict[str, str]] = []

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000  # should match config.WEB_SOCKET_PORT


class RemoteAgentClient:
    def __init__(self, host: str, port: int) -> None:
        self.url = f"http://{host}:{port}"
        self._sio = socketio.AsyncClient()
        self._response_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._user_initiated = False

        @self._sio.on("send_response")
        async def on_response(data: dict) -> None:
            await self._response_queue.put(data)

        @self._sio.on("disconnect")
        async def on_disconnect() -> None:
            if self._user_initiated:
                print_message(
                    "System",
                    "Disconnected from remote backend (client initiated).",
                )
            else:
                print_message(
                    "System",
                    "Disconnected from remote backend"
                    " (server closed the connection).",
                )

    async def connect(self) -> None:
        await self._sio.connect(self.url)

    async def disconnect(self) -> None:
        self._user_initiated = True
        if self._sio.connected:
            await self._sio.disconnect()

    async def query(self, message: str) -> str:
        # Note: matches the typo in web_socket.py event name
        await self._sio.emit("chat_message", {"message": message})
        response = await self._response_queue.get()
        return response.get("message", "Agent failed to respond.")


async def ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def print_message(sender: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {sender}: {message}")


def record_message(sender: str, message: str) -> None:
    chat_history.append(
        {
            "sender": sender,
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
    )


def save_chat(sid: str, fmt: str = "txt") -> str:
    ext = fmt if fmt in {"md", "json"} else "txt"
    filename = f"chat_{sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

    with open(filename, "w") as f:
        if fmt == "json":
            payload = {
                "session_id": sid,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "messages": chat_history,
            }
            json.dump(payload, f, indent=2)
        elif fmt == "md":
            f.write(f"# Chat Session `{sid}`\n\n")
            f.write(
                f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n"
            )
            for entry in chat_history:
                f.write(
                    f"**[{entry['timestamp']}] {entry['sender']}:**"
                    f" {entry['message']}\n\n"
                )
        else:
            for entry in chat_history:
                f.write(
                    f"[{entry['timestamp']}] {entry['sender']}:"
                    f" {entry['message']}\n"
                )

    return filename


async def query_agent_loop(
    debug: bool = False,
    remote_client: RemoteAgentClient | None = None,
) -> None:
    sid = SESSION_ID

    agent = None

    if agent is None and not remote_client:
        from backend.agent.agent import (
            create_agent,
            query_agent_instance,
        )

        agent = create_agent()

    if debug:
        print_message("System", f"Debug mode enabled. Session ID: {sid}")
    if remote_client:
        print_message(
            "System", f"Connected to remote backend at {remote_client.url}"
        )
    print_message("System", "Terminal chat started.")
    print_message("System", "Type '/quit' or '/exit' to stop.")

    try:
        while True:
            user_text = (await ainput("Message: ")).strip()
            command_mode = user_text.startswith("/")

            if not user_text:
                continue

            if user_text.lower() in {"/quit", "/exit", "/q"} and command_mode:
                if not remote_client:
                    from backend.agent.agent import remove_agent_session

                    remove_agent_session(sid)
                break

            if user_text.lower() in {"/help", "/h"} and command_mode:
                print_message(
                    "System",
                    "Available commands: /help, /quit, /exit,"
                    " /save [txt|md|json]",
                )
                continue

            parts = user_text.lower().split()
            if parts[0] in {"/save", "/s"} and command_mode:
                fmt = (
                    parts[1]
                    if len(parts) > 1 and parts[1] in {"txt", "md", "json"}
                    else "txt"
                )
                filename = save_chat(sid, fmt)
                print_message("System", f"Chat history saved to {filename}")
                continue

            record_message("User", user_text)

            if remote_client:
                response = await remote_client.query(user_text)
            else:
                print(f"Message from {sid}: {user_text}", file=sys.stderr)
                response = await query_agent_instance(agent, user_text)
                if response is None:
                    response = "Agent failed to respond."

            print_message("ChatBot", response)
            record_message("ChatBot", response)

    except KeyboardInterrupt:
        print()
        print_message("System", "Interrupted by user.")
    finally:
        if remote_client:
            await remote_client.disconnect()
        print_message("System", "Session closed.")
        sys.exit(0)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal chat client")
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--remote",
        "-r",
        action="store_true",
        help="Connect to a remote backend via WebSocket instead of"
        " running locally",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Remote backend host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Remote backend port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    remote_client = None

    if args.remote:
        if not SOCKETIO_AVAILABLE:
            print(
                "Error: python-socketio is required for remote mode.\n"
                'Run: pip install "python-socketio[asyncio_client]"'
            )
            sys.exit(1)

        remote_client = RemoteAgentClient(args.host, args.port)
        try:
            await remote_client.connect()
        except Exception as e:
            print(f"Failed to connect to {remote_client.url}: {e}")
            sys.exit(1)

    await query_agent_loop(debug=args.debug, remote_client=remote_client)


if __name__ == "__main__":
    asyncio.run(main())
