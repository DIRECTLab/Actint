import json
from fastmcp import Client
from backend.mcp_servers.ais import ais_mcp_server

_tool_str = None


async def get_tool_definitions_str() -> str:
    global _tool_str
    if _tool_str is not None:
        return _tool_str

    async with Client(ais_mcp_server.mcp) as client:
        tools = await client.list_tools()

    lines = []
    for tool in tools:
        lines.append(f"### {tool.name}")
        if tool.description:
            lines.append(tool.description)
        if tool.inputSchema:
            lines.append("Parameters:")
            try:
                lines.append(json.dumps(tool.inputSchema, indent=2))
            except Exception:
                lines.append(str(tool.inputSchema))
        lines.append("")

    _tool_str = "\n".join(lines)
    return _tool_str


async def fetch_information(state):
    request = state.get("tool_request")
    if not request:
        return {}

    name = request.get("tool_name")
    args = request.get("tool_args", {})

    async with Client(ais_mcp_server.mcp) as client:
        result = await client.call_tool(name, args)

    result_str = str(result)

    try:
        structured = result if isinstance(result, dict) else json.loads(result_str)
    except Exception:
        structured = {"raw": result_str}

    history = state.get("tool_history", []) + [{
        "tool": name,
        "args": args,
        "result": structured,
    }]

    thinking = state.get("agent_thinking", []) + [f"Tool {name} executed"]

    return {
        "tool_result": result_str,
        "tool_result_structured": structured,
        "tool_history": history,
        "agent_thinking": thinking,
        "steps": state.get("steps", 0) + 1,
        "tool_request": None,
    }
