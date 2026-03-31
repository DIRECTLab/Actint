from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import os

##### Required pip packages #####
# fastmcp
# smolagents
# 'smolagents[mcp]'

model_id = "Qwen/Qwen2-7B-Instruct"


server_params = StdioServerParameters(
    command="python",
    args=["./server.py"], # Path to your FastMCP server
    cwd=os.getcwd()
)

mcp_client = None



try:
    mcp_client = MCPClient(server_params)
    tools = mcp_client.get_tools()

    model = TransformersModel(model_id=model_id)
    agent = ToolCallingAgent(tools=tools, model=model)

    # result = agent.run("What is the weather like in Logan, Utah?")
    GradioUI(agent).launch()
    # print(f"Agent response: {result}")
finally:
    mcp_client.disconnect()