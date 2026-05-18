import json
from backend.langgraph.common.llm.inference import generate
from .fetch import get_tool_definitions_str


async def analyze(state):
    tool_defs = await get_tool_definitions_str()

    prompt = f"""
You are an ADS-B analysis agent (using AIS tools backend for now).

Rules:
- Output ONLY valid JSON
- If data is missing, call a tool
- Never hallucinate data

Available Tools:
{tool_defs}

User Query:
{state.get("user_query")}

Previous Thoughts:
{state.get("agent_thinking", [])}

Structured Tool Result:
{state.get("tool_result_structured")}

Return JSON:
{{
  "thought": "...",
  "action": "tool" | "finish",
  "tool_name": "...",
  "tool_args": {{}},
  "final_answer": "..."
}}
"""

    raw = await generate(prompt, max_tokens=500)

    try:
        parsed = json.loads(raw)
    except Exception:
        return {"done": True, "final_answer": raw}

    thought = parsed.get("thought")
    action = parsed.get("action")

    thinking = state.get("agent_thinking", [])
    if thought:
        thinking = thinking + [thought]

    updates = {"agent_thinking": thinking}

    if action == "tool":
        updates["tool_request"] = {
            "tool_name": parsed.get("tool_name"),
            "tool_args": parsed.get("tool_args", {}),
        }
    elif action == "finish":
        updates["done"] = True
        updates["final_answer"] = parsed.get("final_answer")

    return updates
