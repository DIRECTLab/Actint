# backend/agent/agent.py
import os
import asyncio
from smolagents import ToolCallingAgent, MCPClient, AgentMaxStepsError, ActionStep, TaskStep, OpenAIModel
from mcp import StdioServerParameters
import sys
from pathlib import Path

from backend.config import config
from backend.mcp_servers.ais import ais_mcp_server
from backend.mcp_servers.adsb import adsb_mcp_server
from backend.event_loop_registry import set_event_loop
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import sys
import socket
import requests


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


if is_port_in_use(4317):
    register(project_name="Actint")
    SmolagentsInstrumentor().instrument()
else:
    print(
        "\x1b[33mPhoenix telemetry server is not running on localhost:4317. Skipping instrumentation.\033[0m",
        file=sys.stderr
    )

def check_openai_health(api_key="dummy") -> str:
    url = f"{config.INFERENCE_SERVER_URL}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return "\033[1;32mAPI is operational and the connection is healthy and serving the following models:\033[0m " + "\n- ".join([model['id'] for model in response.json().get('data', [])])
        else:
            return f"\033[31mAPI returned error code: {response.status_code}\033[0m"
    except requests.exceptions.RequestException as e:
        return f"\033[31mNetwork/Connection failure: {str(e)}\033[0m"


model_id = config.MODEL_ID or ""
print("\033[0;34mModel ID: \033[1;34m" + model_id + "\033[0m")

if config.CONDA_PREFIX:
    python_path = str(Path(config.CONDA_PREFIX) / "bin" / "python")
else:
    python_path = sys.executable

ais_server_params = StdioServerParameters(
    command=python_path,
    args=[ais_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

ais_mcp_client = MCPClient(ais_server_params, structured_output=False)
ais_mcp_tools = ais_mcp_client.get_tools()


# adsb_server_params = StdioServerParameters(
#     command=python_path,
#     args=[adsb_mcp_server.__file__],
#     env=os.environ.copy(),
#     cwd=os.getcwd()
# )

_agent_sessions = {}

def get_or_create_agent(session_id: str, additional_tools: list = []) -> ToolCallingAgent:
    """Creates or retrieves an agent for a given session, injecting relevant tools."""
    if session_id not in _agent_sessions:
        # Base tools that all agents get (e.g., MCP server tools)
        tools = ais_mcp_tools.copy()
        
        # Inject context-specific tools (like UI tools or terminal tools)
        if additional_tools:
            tools.extend(additional_tools)
            
        _agent_sessions[session_id] = ToolCallingAgent(tools=tools, model=model)
        
    return _agent_sessions[session_id]

model = OpenAIModel(
    model_id="local",
    api_base=config.INFERENCE_SERVER_URL,
    api_key=config.MODEL_API_KEY if config.MODEL_API_KEY else ""
)

def remove_agent_session(session_id: str):
    if session_id in _agent_sessions:
        del _agent_sessions[session_id]
