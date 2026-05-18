from backend.langgraph.common.llm.inference import generate
from backend.langgraph.common.llm.model import tokenizer

async def summarize_reasoning(state):
    prompt = f"""
You are an analyst for AIS data and ship tracking.

Go through the AIS data and ship tracking information to analyze the current situation and provide insites.
Focus on the key steps, decisions, and the potential outcomes of the analysis.
Focus on the query given by the user and provide insites related to the query.
It should focus on the potential risks and outcomes of the current situation and
provide a clear and concise analysis of the situation. If you need more information,
you can ask the user for more information, but try to get as much information as possible from
the AIS data and ship tracking information that can be aquired through the tools given.


Rules:
- Be concise
- Do not repeat yourself
- Do not use markdown
- Do not add extra text after the </final> token.
- End your response immediately after the answer use the following text: </final>

Example User Query:
How are you doing today?
ExampleResponse:
I'm doing well, thank you!</final>

User query:
{state["user_query"]}

Provide you analysis based on the AIS data and ship tracking information:
"""
    final_answer = await generate(prompt, max_tokens=500)

    state["agent_thinking"] = state.get("agent_thinking", []) + [final_answer]

    return {"final_answer": final_answer}