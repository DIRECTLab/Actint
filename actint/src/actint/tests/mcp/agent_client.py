import asyncio
import sys
import json
import os
from typing import List
from huggingface_hub import Agent
from huggingface_hub.inference._mcp.types import ServerConfig

async def main():
    # Define the MCP server to connect to (using the stdio fastmcp server from the project)
    servers: List[ServerConfig] = [
        {
            "type": "stdio",
            "command": "python",
            "args": ["actint/src/actint/tests/mcp/server.py"],
            "env": {},
            "cwd": os.getcwd(),
        }
    ]

    # Initialize the Agent
    # We point base_url to our custom FastAPI local inference server
    # Ryu's IP on directlabwifi is 192.168.0.23, and has ports 2000-3000 open
    agent = Agent(
        model="Qwen/Qwen3.5-9B",
        base_url="http://192.168.0.23:2000/",
        servers=servers
    )

    print("Agent initialized. Running prompt...", file=sys.stderr)
    await agent.load_tools()
    print("MCP tools loaded.", file=sys.stderr)
    
    prompt = "What is the weather in Logan, Utah?"

    try:
        async for chunk in agent.run(prompt):
            if hasattr(chunk, "choices"):
                delta_text = ""
                for choice in getattr(chunk, "choices", []):
                    delta = getattr(choice, "delta", None)
                    if delta is not None:
                        delta_text += getattr(delta, "content", "") or ""

                if delta_text:
                    print(delta_text, end="", flush=True, file=sys.stderr)
                else:
                    print(str(chunk), flush=True, file=sys.stderr)
            elif isinstance(chunk, dict):
                print(json.dumps(chunk), flush=True, file=sys.stderr)
            else:
                print(str(chunk), flush=True, file=sys.stderr)

        print("\nStream complete", file=sys.stderr)
    except Exception as e:
        print(f"\nError running agent: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())