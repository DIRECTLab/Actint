import asyncio
import sys
from datetime import datetime
from uuid import uuid4
from sys import argv

from backend.agent.agent import query_agent, remove_agent_session


SESSION_ID = uuid4().hex[:8]  # Generate a short random session ID for terminal users


async def ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def print_message(sender: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {sender}: {message}")


async def query_agent_loop(debug: bool = False) -> None:
    sid = SESSION_ID
    if debug:
        print_message("System", f"Debug mode enabled. Session ID: {sid}")
    print_message("System", "Terminal chat started.")
    print_message("System", "Type '/quit' or '/exit' to stop.")

    try:
        while True:
            user_text = (await ainput("Message: ")).strip()

            if not user_text:
                continue

            if user_text.lower() in {"/quit", "/exit", "/q"}:
                remove_agent_session(sid)
                break

            if user_text.lower() in {"/help", "/h"}:
                print_message("System", "Available commands: /help, /quit, /exit")
                continue

            print(f"Message from {sid}: {user_text}", file=sys.stderr)

            response = await query_agent(
                user_text,
                session_id=sid,
                additional_tools=[],
            )

            if response is None:
                response = "Agent failed to respond."

            print_message("ChatBot", response)

    except KeyboardInterrupt:
        print()
        print_message("System", "Interrupted by user.")
    finally:
        print_message("System", "Session closed.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal chat client")
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--remote", "-r",
        action="store_true",
        help="Connect to a remote backend via WebSocket instead of running locally",
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
    if len(argv) > 1 and argv[1] in {"--debug", "-d"}:
        asyncio.run(query_agent_loop(debug=True))
    else:
        asyncio.run(query_agent_loop())
