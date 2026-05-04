import sys
import socket
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if is_port_in_use(4317):
    register()
    SmolagentsInstrumentor().instrument()
else:
    print("Phoenix telemetry server is not running on localhost:4317. Skipping instrumentation.", file=sys.stderr)

from smolagents import (
    CodeAgent,
    ToolCallingAgent,
    WebSearchTool,
    VisitWebpageTool,
    InferenceClientModel,
)

model = InferenceClientModel()

search_agent = ToolCallingAgent(
    tools=[WebSearchTool(), VisitWebpageTool()],
    model=model,
    name="search_agent",
    description="This is an agent that can do web search.",
)

manager_agent = CodeAgent(
    tools=[],
    model=model,
    managed_agents=[search_agent],
)
manager_agent.run(
    "If the US keeps its 2024 growth rate, how many years will it take for the GDP to double?"
)