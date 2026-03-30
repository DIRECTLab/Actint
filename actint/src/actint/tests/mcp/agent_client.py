import asyncio
import sys
from huggingface_hub import Agent

async def main():
    # Define the MCP server to connect to (using the stdio fastmcp server from the project)
    servers = [
        {
            "type": "stdio",
            "config": {
                "command": "python",
                "args": ["actint/src/actint/tests/mcp/server.py"]
            }
        }
    ]

    # Initialize the Agent
    # We point base_url to our custom FastAPI local inference server
    agent = Agent(
        model="Qwen/Qwen3.5-9B",
        base_url="http://127.0.0.1:8000/",
        servers=servers
    )

    print("Agent initialized. Running prompt...", file=sys.stderr)
    
    # Run the agent (this method handles the tool execution loop implicitly)
    # Note: huggingface_hub.Agent.run() is an async generator or awaits? 
    # Let's use async for safe measure and iterate over its chunks or await it.
    try:
        # Agent.run returns an AsyncGenerator of message chunks
        async for chunk in agent.run("What is the weather in Logan, Utah?"):
            print(chunk, end="", flush=True, file=sys.stderr)
    except Exception as e:
        print(f"\nError running agent: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())