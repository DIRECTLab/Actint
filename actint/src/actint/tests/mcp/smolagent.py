import os
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import sys
from pathlib import Path

##### Required pip packages #####
# fastmcp
# smolagents
# 'smolagents[mcp]'

model_id = "Qwen/Qwen2-7B-Instruct"

# Use actint_env if it exists, otherwise fall back to system python or current env
conda_prefix = os.getenv("CONDA_PREFIX")
if conda_prefix:
    python = str(Path(conda_prefix) / "bin" / "python")
else:
    # Fallback to a hardcoded path or searching for actint_env
    # For now, let's try to find it in the usual place
    actint_env_path = Path("/home/isaacp/miniforge3/envs/actint_env/bin/python")
    if actint_env_path.exists():
        python = str(actint_env_path)
    else:
        python = "python3" # Global fallback

server_params = StdioServerParameters(
    command=python,
    # args=["../../mcp/mcp_server.py"], # Path to your FastMCP server
    args=["smol_mcp_server.py"],
    cwd=os.getcwd()
)

try:
    mcp_client = MCPClient(server_params, structured_output=False)
    tools = mcp_client.get_tools()

    model = TransformersModel(model_id=model_id)
    agent = ToolCallingAgent(tools=tools, model=model)

    result = agent.run("Where is the USS Montgomery?")
    # GradioUI(agent).launch()
    # with open("agent_log.txt", "w") as f:
    #     print(agent.write_memory_to_messages(), file=f)
finally:
    mcp_client.disconnect()