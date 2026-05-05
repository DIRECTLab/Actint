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

model = TransformersModel(
    model_id=model_id,
    max_new_tokens=config.MAX_NEW_TOKENS,
)

adsb_mcp_client = MCPClient(adsb_server_params, structured_output=False)
adsb_mcp_tools = adsb_mcp_client.get_tools()

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

async def query_agent(query: str, session_id: str, additional_tools: list = None):
    """Entry point for both web and terminal to query their respective agent."""
    agent = get_or_create_agent(session_id, additional_tools)
    return agent.run(query, reset=False)

def create_agent(
    additional_tools: list = [],
    
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


def summarize_last_turn(instructions: str, agent: ToolCallingAgent):
    summarization_tools = []  # Define any tools specific to summarization if needed

    agent_memory = agent.memory
    first_step = None
    if not agent_memory: 
        return "Invalid session ID. No existing agent with that ID."
    first_step = None
    if agent_memory.steps:
        for num, step in enumerate(reversed(agent_memory.steps[-config.MAX_AGENT_STEPS:])):
            print(type(step))
            if isinstance(step, TaskStep):
                first_step = len(agent_memory.steps) - num - 1
                break
    else: 
        first_step = 0

    if first_step == None:
        return "Unable to summarize the last turn."

    steps_to_summarize = agent_memory.steps[first_step:]
    prompt = create_prompt(instructions, steps_to_summarize)

    summarizer_agent = ToolCallingAgent(tools=summarization_tools, model=model)
    import time
    start_time = time.time()
    summary = summarizer_agent.run(prompt, reset=True)
    end_time = time.time()
    time_taken = end_time - start_time
    summarized_step = ActionStep(
        model_output=f"Summary of previous operations: {summary}",
        observations="Multi-step execution condensed for memory efficiency.",
        is_final_answer=True,
        timing=time_taken,
        step_number=1,
    )
    del agent_memory.steps[first_step + 1:] #Keep the user's original query, just summarize the AI slop
    agent_memory.steps.append(summarized_step)
    print(summary)
    return "Success"
    

def create_prompt(instructions, steps_to_summarize):
    prompt = instructions
    for num, step in enumerate(steps_to_summarize): 
        prompt += f"\n\n==Step {num + 1}==\n"
        if getattr(step, 'task', None):
            prompt += f"Task:\n{step.task}\n\n"
        if getattr(step, 'model_output', None):
            prompt += f"Model Thought:\n{step.model_output}\n\n"
        if getattr(step, 'tool_calls', None):
            prompt += f"Tool Calls:\n{step.tool_calls}\n\n"
        if getattr(step, 'model_action', None):
            prompt += f"Model Action:\n{step.model_action}\n\n"
        if getattr(step, 'action_output', None):
            prompt += f"Action Output:{step.action_output}\n\n"
        if getattr(step, 'final_response', None):
            prompt += f"Final Response:\n{step.final_response}"

    return prompt
