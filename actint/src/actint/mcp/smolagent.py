import os
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import sys
from pathlib import Path
from actint.mcp import mcp_server
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

register(project_name="actint")
SmolagentsInstrumentor().instrument()

##### Required pip packages #####
# fastmcp
# smolagents
# 'smolagents[mcp]'

model_id = "Qwen/Qwen3.5-9B"
# model_id = "Qwen/Qwen2-7B-Instruct"

conda_prefix = os.getenv("CONDA_PREFIX")
python = str(Path(conda_prefix) / "bin" / "python")


server_params = StdioServerParameters(
    command=python,
    args=[mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

try:
    mcp_client = MCPClient(server_params, structured_output=False)
    tools = mcp_client.get_tools()

    model = TransformersModel(model_id=model_id)
    agent = ToolCallingAgent(tools=tools, model=model)

    result = agent.run("Are there any anomolies in the data?")
    # GradioUI(agent).launch()
    # with open("agent_log.txt", "w") as f:
    #     print(agent.write_memory_to_messages(), file=f)
finally:
    mcp_client.disconnect()