import os
from smolagents import ToolCallingAgent, TransformersModel, MCPClient, GradioUI
from mcp import StdioServerParameters
import sys
from pathlib import Path

from transformers import AutoTokenizer
from actint.mcp import mcp_server
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor


register(project_name="actint")
SmolagentsInstrumentor().instrument()

#model_id = "Qwen/Qwen3.5-9B"
model_id = "Qwen/Qwen2-7B-Instruct"

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

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.padding_side = "left"

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token  #The pad_token is the padding token, AI processes things in chunks, so this is just filler so everything is the same chunk size. This is put on the left side (as described in previous code)
                                                   #The eos_token is just the end of sentence token. It describes when a sentence has ended.
    model = TransformersModel(
        model_id=model_id,
        max_new_tokens=4096,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    model.tokenizer = tokenizer 
    agent = ToolCallingAgent(tools=tools, model=model)

    if ('Qwen3.5' in model_id):
        template_path = Path(__file__).with_name("qwen_system_prompt_template.jinja")
        qwen_system_prompt_template = template_path.read_text(encoding="utf-8")
        agent.prompt_templates["system_prompt"] = qwen_system_prompt_template

    result = agent.run("Where is the USS Montgomery right now?", reset=False)
    # result2 = agent.run("Do you know the muffin man?")


    # Time to make a chat interface: What to do:
    # Store the previous chat messsages and give the LLM a get_previous_messages tool. 
    # It would probably be good if the LLM had one tool to get the last 10 or so messages, and another to search over the previous messages..
    # It might be good to use a RAG here so that the LLM can fetch the most relavant information.
    # The LLM will also need the various functions to manipulate the map as tools.
    # This whole thing shouuld be in a loop      wait for user input -> answer -> wait for user input


    # GradioUI(agent).launch()
finally:
    mcp_client.disconnect()