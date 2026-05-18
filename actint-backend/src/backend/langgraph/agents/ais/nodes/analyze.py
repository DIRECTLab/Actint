import json
from backend.langgraph.common.llm.inference import generate
from backend.langgraph.agents.ais.nodes.fetch import get_tool_definitions_str


async def analyze(state):
    tool_defs = await get_tool_definitions_str()

    prompt = f"""
You are an AIS analysis agent.

You MUST decide whether to call a tool or finish.

Rules:
- Output ONLY valid JSON
- Do not include any text outside JSON
- If information is missing, call a tool
- Never guess when tools are available

Available Tools:
{tool_defs}

User Query:
{state.get("user_query")}

Previous Thoughts:
{state.get("agent_thinking", [])}

Last Tool Result:
{state.get("tool_result")}

Structured Tool Result:
{state.get("tool_result_structured")}

Tool History:
{state.get("tool_history", [])}

Return JSON in this format:
{{
  "thought": "...",
  "action": "tool" | "finish",
  "tool_name": "...",
  "tool_args": {{}},
  "final_answer": "..."
}}
"""

    async def call_model(p):
        return await generate(p, max_tokens=500)

    raw = await call_model(prompt)

    def try_parse(s):
        try:
            return json.loads(s), None
        except Exception as e:
            return None, str(e)

    parsed, err = try_parse(raw)

    def validate_schema(obj):
        if not isinstance(obj, dict):
            return False, "Output is not a JSON object"
        if "action" not in obj or "thought" not in obj:
            return False, "Missing required keys"
        if obj["action"] not in ("tool", "finish"):
            return False, "Invalid action"
        if obj["action"] == "tool":
            if not obj.get("tool_name"):
                return False, "Missing tool_name for tool action"
            if not isinstance(obj.get("tool_args", {}), dict):
                return False, "tool_args must be object"
        if obj["action"] == "finish":
            if "final_answer" not in obj:
                return False, "Missing final_answer for finish action"
        return True, None

    valid = False
    if parsed is not None:
        valid, err = validate_schema(parsed)

    # Retry once if invalid JSON OR schema
    if parsed is None or not valid:
        retry_prompt = prompt + """

Your previous response was invalid JSON.
Return ONLY valid JSON. No extra text, no markdown, no explanations.
Ensure keys and quotes are correct.
Also ensure it follows the required schema exactly.
"""
        raw_retry = await call_model(retry_prompt)
        parsed, err = try_parse(raw_retry)
        if parsed is not None:
            valid, err = validate_schema(parsed)

        if parsed is None or not valid:
            return {
                "done": True,
                "final_answer": raw_retry,
            }

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
