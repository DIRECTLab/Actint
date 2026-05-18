from backend.langgraph.common.llm.inference import generate
from backend.langgraph.common.llm.model import tokenizer
from backend.mcp_servers.ais import ais_mcp_server

async def fetch_information(state):

    ais_mcp_server.

    prompt = f"""
You are information gatherer for the AIS Agent.

Based on the information given by the tools and the AIS Agent, get the information
together from the database and pass them back to the AIS Agent. Focus on getting the
relevent information together and provide it in a markdown format so the Agent
can easily read and understand it.

Rules:
- Be concise
- Do not repeat yourself
- End your response immediately after the answer use the following text: </final>

Example User Query:
How are you doing today?
ExampleResponse:
I'm doing well, thank you!</final>

Availible Tools:

User query:
{state["user_query"]}

AIS Agent's Request:
{state["agent_thinking"][-1] if state["agent_thinking"] else "No request from the AIS Agent yet."}

Provide your summary of the AIS Agent's reasoning and actions in response to the user's query:
"""
    final_answer = await generate(prompt, max_tokens=500)
    return {"final_answer": final_answer}