import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import sys

##### Required pip packages #####
# fastmcp
# smolagents
# 'smolagents[mcp]'

model_id = "Qwen/Qwen2-7B-Instruct"


server_params = StdioServerParameters(
    command="python",
    args=["../../mcp/mcp_server.py"], # Path to your FastMCP server
    cwd=os.getcwd()
)

try:
    mcp_client = MCPClient(server_params)
    tools = mcp_client.get_tools()

    model = TransformersModel(model_id=model_id)
    agent = ToolCallingAgent(tools=tools, model=model)

    result = agent.run("Where is the USS Kidd?")
    # GradioUI(agent).launch()
    with open("agent_log.txt", "w") as f:
        print(agent.write_memory_to_messages(), file=f)
    # print(f"Agent response: {result}")
finally:
    mcp_client.disconnect()