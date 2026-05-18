from backend.langgraph.common.llm.inference import generate


async def summarize_reasoning(state):
    prompt = f"""
Summarize the ADS-B agent findings.

User Query:
{state.get("user_query")}

Reasoning:
{state.get("agent_thinking", [])}

Provide a concise final answer.
"""

    final = await generate(prompt, max_tokens=300)
    return {"final_answer": final}
