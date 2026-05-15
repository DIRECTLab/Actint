# backend/agent/agent.py
import os
import asyncio
import sys
from backend.config import config
from pathlib import Path

from smolagents import ToolCallingAgent, CodeAgent, VLLMModel, MCPClient, AgentMaxStepsError, ActionStep, TaskStep
from mcp import StdioServerParameters
from backend.mcp_servers.ais import ais_mcp_server
from backend.mcp_servers.adsb import adsb_mcp_server
from backend.event_loop_registry import set_event_loop
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
import socket


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


if is_port_in_use(4317):
    register(project_name="Multiagent")
    SmolagentsInstrumentor().instrument()
else:
    print(
        "\x1b[33mPhoenix telemetry server is not running on localhost:4317. Skipping instrumentation.\033[0m",
        file=sys.stderr
    )

model_id = config.MODEL_ID
print("\033[0;34mModel ID: \033[1;34m" + model_id + "\033[0m")

if config.CONDA_PREFIX:
    python_path = str(Path(config.CONDA_PREFIX) / "bin" / "python")
else:
    python_path = sys.executable


ais_server_params = StdioServerParameters(
    command=python_path,
    args=[ais_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd(),
)

ais_mcp_client = MCPClient(ais_server_params, structured_output=False)
ais_mcp_tools = ais_mcp_client.get_tools()


adsb_server_params = StdioServerParameters(
    command=python_path,
    args=[adsb_mcp_server.__file__],
    env=os.environ.copy(),
    cwd=os.getcwd(),
)

adsb_mcp_client = MCPClient(adsb_server_params, structured_output=False)
adsb_mcp_tools = adsb_mcp_client.get_tools()

def init_model() -> VLLMModel:
    model_kwargs={}
    # We have to limit the context length to fit gemma-4-31B on a blackwell
    if config.MODEL_ID == 'google/gemma-4-31B-it':
        model_kwargs={'max_model_len': 131392}

    return VLLMModel(
        model_id=config.MODEL_ID,
        model_kwargs=model_kwargs
    )

def create_agent(
    model,
    additional_tools: list = []
) -> CodeAgent:
    """Creates an agent, injecting relevant tools."""
    tools = []
    # tools += ais_mcp_tools
    # tools += adsb_mcp_tools
    
    ais_agent = CodeAgent(
        tools=ais_mcp_tools,
        model=model,
        max_steps=20,
        name="martime_data_agent",
        description="Can query a database of AIS information (including position, heading, speed, etc.) and do calculations with that data."
    )

    adsb_agent = CodeAgent(
        tools=adsb_mcp_tools,
        model=model,
        max_steps=20,
        name="aviation_data_agent",
        description="Can query a database of ADS-B information and do calculations with that data."
    )

    # search_agent = CodeAgent(
    #     tools=[WebSearchTool()],
    #     model=get_model(),
    #     max_steps=10,
    #     name="web_search_agent",
    #     description="Can search the web for information and summarize results."
    # )

    managed_agents = [ais_agent, adsb_agent]
    # managed_agents = []
    
    if additional_tools:
        tools.extend(additional_tools)
        # map_agent = ToolCallingAgent(
        #     tools=additional_tools,
        #     model=get_model(),
        #     max_steps=10,
        #     name="map_ui_agent",
        #     description="Can show things to the user on a map. Can move, zoom, and draw basic shapes on the map."
        # )
        # managed_agents.append(map_agent)

    
    return CodeAgent(tools=tools, model=model, managed_agents=managed_agents)

async def query_agent_instance(
    agent: CodeAgent,
    query: str,
) -> str:
    """Entry point for both web and terminal to query an agent instance."""

    loop = asyncio.get_running_loop()
    set_event_loop(loop)  # Register before entering the thread so tools can reach it

    try:
        result = await loop.run_in_executor(
            None, lambda: agent.run(query, reset=False)
        )
        return result
    except AgentMaxStepsError:
        print(f"Agent hit max steps.", file=sys.stderr)
        return "Agent failed to respond: maximum steps exceeded."
    except Exception as e:
        print(f"Agent error: {e}", file=sys.stderr)
        return f"Agent encountered an error: {str(e)}"

#======================================Summarization Agent==================================#

def summarize_last_turn(instructions: str, agent: CodeAgent):
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

    summarizer_agent = CodeAgent(tools=summarization_tools, model=agent.model)
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
