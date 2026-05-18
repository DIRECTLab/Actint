from backend.langgraph.common.llm.inference import generate
from backend.langgraph.common.llm.model import tokenizer

async def summarize_reasoning(state):
    prompt = f"""
You are the summarizer for the AIS .

Write a concise summary of the thinking, process, and actions taken by the AIS Agent
in response to the user's query. Focus on the key steps, decisions, and the potenial outcomes
of the analysis. The summary should be clear, informative, and capture the essence of the AIS
Agent's reasoning and actions in a way that is easy for the user to understand.


Rules:
- Be concise
- Do not repeat yourself
- Do not use markdown
- Do not add extra text
- End your response immediately after the answer use the following text: </final>

Example User Query:
How are you doing today?
ExampleResponse:
I'm doing well, thank you!</final>

User query:
{state["user_query"]}

Agent reasoning:
{state.get("agent_thinking", [])}

Provide your summary of the AIS Agent's reasoning and actions in response to the user's query:
"""
    final_answer = await generate(prompt, max_tokens=500)
    return {"final_answer": final_answer}
