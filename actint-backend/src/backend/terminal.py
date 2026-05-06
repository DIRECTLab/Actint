import asyncio
import json
import sys
from datetime import datetime
from uuid import uuid4
from sys import argv

try:
    import readline  # noqa: F401 -- enables up-arrow input history automatically
except ImportError:
    # readline is Unix/macOS only. Install pyreadline3 on Windows.
    pass

from backend.agent.agent import query_agent, remove_agent_session


SESSION_ID = uuid4().hex[:8]

chat_history: list[dict[str, str]] = []


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
    filename = (
        f"chat_{sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    )

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
                print_message(
                    "System",
                    "Available commands: /help, /quit, /exit, /save [txt|md|json]",
                )
                continue

            parts = user_text.lower().split()
            if parts[0] in {"/save", "/s"}:
                fmt = (
                    parts[1]
                    if len(parts) > 1 and parts[1] in {"txt", "md", "json"}
                    else "txt"
                )
                filename = save_chat(sid, fmt)
                print_message("System", f"Chat history saved to {filename}")
                continue

            print(f"Message from {sid}: {user_text}", file=sys.stderr)
            record_message("User", user_text)

            response = await query_agent(
                user_text,
                session_id=sid,
                additional_tools=[],
            )

            if response is None:
                response = "Agent failed to respond."

            print_message("ChatBot", response)
            record_message("ChatBot", response)

    except KeyboardInterrupt:
        print()
        print_message("System", "Interrupted by user.")
    finally:
        print_message("System", "Session closed.")


if __name__ == "__main__":
    if len(argv) > 1 and argv[1] in {"--debug", "-d"}:
        asyncio.run(query_agent_loop(debug=True))
    else:
        asyncio.run(query_agent_loop())