import os
from smolagents import ToolCallingAgent, TransformersModel, MCPClient
from mcp import StdioServerParameters
import sys
from pathlib import Path

from backend.mcp_servers.ais import ais_mcp_server
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from backend.transport.defaults import sio
from backend.native_tools.map_edit_tools import ZoomTool, DrawRectangleTool, DrawCircleTool, DrawLineTool
import sys
import socket

# Set the Hugging Face cache directory before importing Transformers
# os.environ["HF_HOME"] = os.path.expandvars("/scratch/$USER/huggingface_cache")

# Register Phoenix instrumentation
def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Register Phoenix instrumentation if server is running
if is_port_in_use(4317):
    register(project_name="Map_Actint")
    SmolagentsInstrumentor().instrument()
else:
    print("Phoenix telemetry server is not running on localhost:4317. Skipping instrumentation.", file=sys.stderr)


model_id = "Qwen/Qwen3.5-9B"
#model_id = "Qwen/Qwen2-7B-Instruct"

conda_prefix = os.getenv("CONDA_PREFIX")
python = str(Path(conda_prefix) / "bin" / "python")

# Initialize MCP server
server_params = StdioServerParameters(
    command=python,
    args=[ais_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

mcp_client = MCPClient(server_params, structured_output=False)
ais_mcp_tools = mcp_client.get_tools()


model = TransformersModel(
    model_id=model_id,
    max_new_tokens=4096,
)


user_agent_dict = {}

async def user_agent_query(query: str, sid: str):
    if sid not in user_agent_dict:
        user_tools = ais_mcp_tools + [ZoomTool(sid, sio), DrawRectangleTool(sid, sio), DrawCircleTool(sid, sio), DrawLineTool(sid, sio)]
        user_agent_dict[sid] = ToolCallingAgent(tools=user_tools, model=model)

    result = user_agent_dict[sid].run(query, reset=False)
    return result

def remove_user_agent(sid: str):
    if sid in user_agent_dict:
        del user_agent_dict[sid]