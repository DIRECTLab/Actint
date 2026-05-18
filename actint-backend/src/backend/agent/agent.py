# backend/agent/agent.py
import os
import asyncio
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, AgentMaxStepsError
from mcp import StdioServerParameters
import sys
from pathlib import Path

from backend.config import config
from backend.mcp_servers.ais import ais_mcp_server
from backend.event_loop_registry import set_event_loop
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import socket


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


if is_port_in_use(4317):
    register(project_name="Map_Actint")
    SmolagentsInstrumentor().instrument()
else:
    print(
        "Phoenix telemetry server is not running on localhost:4317. Skipping instrumentation.",
        file=sys.stderr
    )
<<<<<<< HEAD

model_id = config.MODEL_ID
print("Model ID: " + model_id)
=======
>>>>>>> d8efec1 (Alex/web socket fix (#3))

model_id = config.MODEL_ID
print("Model ID: " + model_id)

if config.CONDA_PREFIX:
    python_path = str(Path(config.CONDA_PREFIX) / "bin" / "python")
else:
    python_path = sys.executable

server_params = StdioServerParameters(
    command=python_path,
    args=[ais_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

mcp_client = MCPClient(server_params, structured_output=False)
ais_mcp_tools = mcp_client.get_tools()

model = TransformersModel(
    model_id=model_id,
    max_new_tokens=config.MAX_NEW_TOKENS,
)

<<<<<<< HEAD
_agent_sessions = {}

=======
>>>>>>> d8efec1 (Alex/web socket fix (#3))
_agent_sessions = {}


def get_or_create_agent(
    session_id: str, additional_tools: list = []
) -> ToolCallingAgent:
    """Creates or retrieves an agent for a given session, injecting relevant tools."""
    if session_id not in _agent_sessions:
        tools = ais_mcp_tools.copy()
        if additional_tools:
            tools.extend(additional_tools)
        _agent_sessions[session_id] = ToolCallingAgent(tools=tools, model=model)
    return _agent_sessions[session_id]


async def query_agent(
    query: str,
    session_id: str,
    additional_tools: list = None,
) -> str:
    """Entry point for both web and terminal to query their respective agent."""

    loop = asyncio.get_running_loop()
    set_event_loop(loop)  # Register before entering the thread so tools can reach it

    agent = get_or_create_agent(session_id, additional_tools or [])

    try:
        result = await loop.run_in_executor(
            None, lambda: agent.run(query, reset=False)
        )
        return result
    except AgentMaxStepsError:
        print(f"[session={session_id}] Agent hit max steps.", file=sys.stderr)
        return "Agent failed to respond: maximum steps exceeded."
    except Exception as e:
        print(f"[session={session_id}] Agent error: {e}", file=sys.stderr)
        return f"Agent encountered an error: {str(e)}"


def remove_agent_session(session_id: str):
    if session_id in _agent_sessions:
        del _agent_sessions[session_id]