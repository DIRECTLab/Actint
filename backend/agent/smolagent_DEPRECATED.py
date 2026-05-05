import os
import socket
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import sys
from pathlib import Path
from backend.mcp_servers.ais import ais_mcp_server
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if is_port_in_use(4317):
    register(project_name="actint")
    SmolagentsInstrumentor().instrument()
else:
    print("Phoenix telemetry server is not running on localhost:4317. Skipping instrumentation.", file=sys.stderr)

model_id = "Qwen/Qwen3.5-9B"
# model_id = "Qwen/Qwen2-7B-Instruct"

conda_prefix = os.getenv("CONDA_PREFIX")
python = str(Path(conda_prefix) / "bin" / "python")



server_params = StdioServerParameters(
    command=python,
    args=[ais_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd()
)

try:
    mcp_client = MCPClient(server_params, structured_output=False)
    tools = mcp_client.get_tools()

    model = TransformersModel(model_id=model_id, max_new_tokens=4096)

    agent = ToolCallingAgent(tools=tools, model=model)

    if ('Qwen3.5' in model_id):
        template_path = Path(__file__).with_name("qwen_system_prompt_template.jinja")
        qwen_system_prompt_template = template_path.read_text(encoding="utf-8")
        agent.prompt_templates["system_prompt"] = qwen_system_prompt_template

    result = agent.run("Where is the USS Montgomery currently heading?")

    # GradioUI(agent).launch()
finally:
    mcp_client.disconnect()