import os
from smolagents import ToolCallingAgent, TransformersModel, MCPClient
from mcp import StdioServerParameters
import sys
from pathlib import Path
from actint.mcp import mcp_server
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

# Register Phoenix instrumentation
register(project_name="Map_Actint")
SmolagentsInstrumentor().instrument()

#model_id = "Qwen/Qwen3.5-9B"
model_id = "Qwen/Qwen2-7B-Instruct"

conda_prefix = os.getenv("CONDA_PREFIX")
python = str(Path(conda_prefix) / "bin" / "python")

# Initialize MCP server
server_params = StdioServerParameters(
    command=python,
    args=[mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

mcp_client = MCPClient(server_params, structured_output=False)
tools = mcp_client.get_tools()

# Load model and create agent
model = TransformersModel(model_id=model_id)
agent = ToolCallingAgent(tools=tools, model=model)

def process_chat_message(sid: str, message: str) -> str:
    result = agent.run(message, return_full_result=True, reset=False)
    print("Agent Responsed", file=sys.stderr)
    if result.output:
        return result.output
    else:
        return f"Response Failed. Agent state: {result.state}"





# Pseudocode: 
#  Create a global LLM that all the different toolCallingAgents can reference.
#  Create a function that handles every user that gets on.  
#  For every user, give them a toolCallingAgent, and allow them to make queries with all the tools in the MCP server. 
#  Return the answer the tool calling agent returns to them. Might need to figure out a way to deal with the thinking behaviors of the ceratin LLM.