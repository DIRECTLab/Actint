import asyncio
import sys
from datetime import datetime

from backend.agent.agent import get_available_tool_names, remove_user_agent, user_agent_query


SESSION_ID = "tui-session"


async def ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def print_message(sender: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {sender}: {message}")


async def query_agent_loop() -> None:
    sid = SESSION_ID
    print_message("System", "Terminal chat started.")
    print_message("System", "Type '/quit' or '/exit' to stop.")

    try:
        while True:
            user_text = (await ainput("Message: ")).strip()

            if not user_text:
                continue

            if user_text.lower() in {"/quit", "/exit"}:
                break

            if user_text.lower() in {"/help", "/h"}:
                print_message("System", "Available commands: /help, /quit, /exit")
                continue

            print(f"Message from {sid}: {user_text}", file=sys.stderr)

            allowed_tools = set(get_available_tool_names()["ais"])

            response = await user_agent_query(
                user_text,
                sid=sid,
                allowed_tools=allowed_tools,
            )

            if response is None:
                response = "Agent failed to respond."

            print_message("ChatBot", response)

    except KeyboardInterrupt:
        print()
        print_message("System", "Interrupted by user.")
    finally:
        remove_user_agent(sid)
        print_message("System", "Session closed.")


if __name__ == "__main__":
    asyncio.run(query_agent_loop())