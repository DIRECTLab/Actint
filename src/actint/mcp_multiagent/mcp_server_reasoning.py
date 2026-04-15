"""
MCP server for the reasoning manager agent.

This server intentionally exposes no direct database or vessel-intelligence
retrieval tools. It provides only coordination helpers so the reasoning agent
must delegate factual retrieval to the SQL agent.
"""

import json
import os
import sys
import atexit
import io
import re
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

from mcp import StdioServerParameters
from fastmcp import FastMCP
from smolagents import MCPClient, ToolCallingAgent, TransformersModel

from actint.mcp_multiagent import mcp_server_map, mcp_server_math, mcp_server_sql

mcp = FastMCP("AIS Reasoning Coordinator", "1.0.0")

_SQL_AGENT: ToolCallingAgent | None = None
_SQL_MCP_CLIENT: MCPClient | None = None
_SQL_MODEL_ID: str | None = None
SQL_LOG_PATH = Path(os.getcwd()) / "sql_agent.log"

_MAP_AGENT: ToolCallingAgent | None = None
_MAP_MCP_CLIENT: MCPClient | None = None
_MAP_MODEL_ID: str | None = None
MAP_LOG_PATH = Path(os.getcwd()) / "map_agent.log"

_MATH_AGENT: ToolCallingAgent | None = None
_MATH_MCP_CLIENT: MCPClient | None = None
_MATH_MODEL_ID: str | None = None
MATH_LOG_PATH = Path(os.getcwd()) / "math_agent.log"
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
OTEL_NOISE_MARKERS = (
    "Transient error StatusCode.UNAVAILABLE encountered while exporting traces",
    "Failed to export traces to localhost:4317",
)


def _load_map_template() -> str:
    template_path = Path(__file__).with_name("qwen_system_prompt_map.jinja")
    return template_path.read_text(encoding="utf-8")


def _load_math_template() -> str:
    template_path = Path(__file__).with_name("qwen_system_prompt_math.jinja")
    return template_path.read_text(encoding="utf-8")


def _resolve_python_executable() -> str:
    conda_prefix = os.getenv("CONDA_PREFIX")
    if conda_prefix:
        candidate = Path(conda_prefix) / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _clean_log_text(text: str) -> str:
    """Make verbose specialist logs easier to read as plain text."""
    text = ANSI_ESCAPE_RE.sub("", text)

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if any(marker in line for marker in OTEL_NOISE_MARKERS):
            continue

        stripped = line.strip()
        if stripped and all(ch in "─━│╭╮╰╯-=" for ch in stripped):
            continue

        cleaned_lines.append(line.rstrip())

    collapsed: list[str] = []
    prev_blank = False
    for line in cleaned_lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = is_blank

    output = "\n".join(collapsed).strip()
    return output + "\n" if output else ""


def _build_sql_agent_singleton(model_id: str) -> ToolCallingAgent:
    global _SQL_AGENT, _SQL_MCP_CLIENT, _SQL_MODEL_ID

    if _SQL_AGENT is not None:
        return _SQL_AGENT

    python = _resolve_python_executable()
    server_params = StdioServerParameters(
        command=python,
        args=[mcp_server_sql.__file__],
        env=os.environ.copy(),
        cwd=os.getcwd(),
    )

    _SQL_MCP_CLIENT = MCPClient(server_params, structured_output=False)
    sql_tools = [
        tool
        for tool in _SQL_MCP_CLIENT.get_tools()
        if getattr(tool, "name", "") in {"get_database_info", "query_database"}
    ]

    if len(sql_tools) < 2:
        raise RuntimeError(
            "SQL specialist could not find expected tools: "
            "get_database_info, query_database"
        )

    model = TransformersModel(model_id=model_id)
    _SQL_AGENT = ToolCallingAgent(
        tools=sql_tools,
        model=model,
        name="sql_agent",
        verbosity_level=2,
        description=(
            "Specialist SQL agent. Use read-only SQL tools and return concise "
            "natural-language answers grounded in query results."
        ),
    )
    _SQL_MODEL_ID = model_id
    return _SQL_AGENT


def _ask_sql_agent(question: str, model_id: str) -> str:
    global _SQL_MODEL_ID
    try:
        sql_agent = _build_sql_agent_singleton(model_id)
        if _SQL_MODEL_ID and model_id != _SQL_MODEL_ID:
            # Keep one long-lived SQL agent instance for stability and low overhead.
            pass
        # MCP stdio requires stdout to contain only JSON-RPC messages.
        # Capture trace output for debugging into sql_agent.log.
        sql_trace = io.StringIO()
        with redirect_stdout(sql_trace), redirect_stderr(sql_trace):
            result = sql_agent.run(question)
        SQL_LOG_PATH.write_text(_clean_log_text(sql_trace.getvalue()), encoding="utf-8")
        return str(result)
    except Exception as e:
        return json.dumps({"error": f"SQL specialist call failed: {str(e)}"})


def _build_map_agent_singleton(model_id: str) -> ToolCallingAgent:
    global _MAP_AGENT, _MAP_MCP_CLIENT, _MAP_MODEL_ID

    if _MAP_AGENT is not None:
        return _MAP_AGENT

    python = _resolve_python_executable()
    server_params = StdioServerParameters(
        command=python,
        args=[mcp_server_map.__file__],
        env=os.environ.copy(),
        cwd=os.getcwd(),
    )

    _MAP_MCP_CLIENT = MCPClient(server_params, structured_output=False)
    map_tools = [
        tool
        for tool in _MAP_MCP_CLIENT.get_tools()
        if getattr(tool, "name", "")
        in {
            "get_location_context",
            "get_distance_between",
            "identify_maritime_region",
            "find_nearest_port",
            "find_nearest_waterway",
        }
    ]

    if len(map_tools) < 5:
        raise RuntimeError(
            "Map specialist could not find expected tools: get_location_context, "
            "get_distance_between, identify_maritime_region, find_nearest_port, "
            "find_nearest_waterway"
        )

    model = TransformersModel(model_id=model_id)
    _MAP_AGENT = ToolCallingAgent(
        tools=map_tools,
        model=model,
        name="map_agent",
        verbosity_level=2,
        description=(
            "Specialist map agent. Use maritime geospatial tools and return concise "
            "natural-language answers grounded in tool results."
        ),
    )
    if "Qwen3.5" in model_id:
        map_template = _load_map_template()
        _MAP_AGENT.prompt_templates["system_prompt"] = map_template
    _MAP_MODEL_ID = model_id
    return _MAP_AGENT


def _ask_map_agent(question: str, model_id: str) -> str:
    global _MAP_MODEL_ID
    try:
        map_agent = _build_map_agent_singleton(model_id)
        if _MAP_MODEL_ID and model_id != _MAP_MODEL_ID:
            # Keep one long-lived map agent instance for stability and low overhead.
            pass
        map_trace = io.StringIO()
        with redirect_stdout(map_trace), redirect_stderr(map_trace):
            result = map_agent.run(question)
        MAP_LOG_PATH.write_text(_clean_log_text(map_trace.getvalue()), encoding="utf-8")
        return str(result)
    except Exception as e:
        return json.dumps({"error": f"Map specialist call failed: {str(e)}"})


def _build_math_agent_singleton(model_id: str) -> ToolCallingAgent:
    global _MATH_AGENT, _MATH_MCP_CLIENT, _MATH_MODEL_ID

    if _MATH_AGENT is not None:
        return _MATH_AGENT

    python = _resolve_python_executable()
    server_params = StdioServerParameters(
        command=python,
        args=[mcp_server_math.__file__],
        env=os.environ.copy(),
        cwd=os.getcwd(),
    )

    _MATH_MCP_CLIENT = MCPClient(server_params, structured_output=False)
    math_tools = _MATH_MCP_CLIENT.get_tools()

    if len(math_tools) < 8:
        raise RuntimeError("Math specialist did not expose expected toolset")

    model = TransformersModel(model_id=model_id)
    _MATH_AGENT = ToolCallingAgent(
        tools=math_tools,
        model=model,
        name="math_agent",
        verbosity_level=2,
        description=(
            "Specialist math agent. Use quantitative tools and return concise "
            "natural-language answers grounded in computations."
        ),
    )
    if "Qwen3.5" in model_id:
        math_template = _load_math_template()
        _MATH_AGENT.prompt_templates["system_prompt"] = math_template
    _MATH_MODEL_ID = model_id
    return _MATH_AGENT


def _ask_math_agent(question: str, model_id: str) -> str:
    global _MATH_MODEL_ID
    try:
        math_agent = _build_math_agent_singleton(model_id)
        if _MATH_MODEL_ID and model_id != _MATH_MODEL_ID:
            # Keep one long-lived math agent instance for stability and low overhead.
            pass
        math_trace = io.StringIO()
        with redirect_stdout(math_trace), redirect_stderr(math_trace):
            result = math_agent.run(question)
        MATH_LOG_PATH.write_text(_clean_log_text(math_trace.getvalue()), encoding="utf-8")
        return str(result)
    except Exception as e:
        return json.dumps({"error": f"Math specialist call failed: {str(e)}"})


def _shutdown_sql_singleton() -> None:
    global _SQL_MCP_CLIENT
    if _SQL_MCP_CLIENT is not None:
        _SQL_MCP_CLIENT.disconnect()
        _SQL_MCP_CLIENT = None


def _shutdown_map_singleton() -> None:
    global _MAP_MCP_CLIENT
    if _MAP_MCP_CLIENT is not None:
        _MAP_MCP_CLIENT.disconnect()
        _MAP_MCP_CLIENT = None


def _shutdown_math_singleton() -> None:
    global _MATH_MCP_CLIENT
    if _MATH_MCP_CLIENT is not None:
        _MATH_MCP_CLIENT.disconnect()
        _MATH_MCP_CLIENT = None


atexit.register(_shutdown_sql_singleton)
atexit.register(_shutdown_map_singleton)
atexit.register(_shutdown_math_singleton)


@mcp.tool()
def get_reasoning_contract() -> str:
    """Return the reasoning agent operating contract.

    Returns:
        str: JSON policy payload defining delegation behavior.
    """
    contract = {
        "agent_role": "reasoning_manager",
        "must_delegate_data_retrieval_to": ["sql_agent", "map_agent", "math_agent"],
        "must_not": [
            "invent vessel facts",
            "claim unseen SQL evidence",
            "issue direct SQL queries",
        ],
        "expected_output": [
            "answer the user question first",
            "include key supporting facts from SQL results",
            "state uncertainty when evidence is incomplete",
        ],
    }
    return json.dumps(contract, indent=2)


@mcp.tool()
def health() -> str:
    """Return server health metadata for orchestration checks."""
    payload = {
        "status": "healthy",
        "server": "AIS Reasoning Coordinator",
        "sql_agent_initialized": _SQL_AGENT is not None,
        "sql_model_id": _SQL_MODEL_ID,
        "map_agent_initialized": _MAP_AGENT is not None,
        "map_model_id": _MAP_MODEL_ID,
        "math_agent_initialized": _MATH_AGENT is not None,
        "math_model_id": _MATH_MODEL_ID,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def ask_sql_specialist(question: str, model_id: str = "Qwen/Qwen3.5-9B") -> str:
    """Ask the SQL specialist agent a natural-language data question.

    Args:
        question (str): Data question to answer using SQL tools.
        model_id (str): Model used by the SQL specialist.

    Returns:
        str: Natural-language response from the SQL specialist agent.
    """
    prompt = (question or "").strip()
    if not prompt:
        return json.dumps({"error": "question is required"})
    return _ask_sql_agent(prompt, model_id)


@mcp.tool()
def ask_map_specialist(question: str, model_id: str = "Qwen/Qwen3.5-9B") -> str:
    """Ask the map specialist agent a maritime geospatial question.

    Args:
        question (str): Geospatial/maritime context question.
        model_id (str): Model used by the map specialist.

    Returns:
        str: Natural-language response from the map specialist agent.
    """
    prompt = (question or "").strip()
    if not prompt:
        return json.dumps({"error": "question is required"})
    return _ask_map_agent(prompt, model_id)


@mcp.tool()
def ask_math_specialist(question: str, model_id: str = "Qwen/Qwen3.5-9B") -> str:
    """Ask the math specialist agent a quantitative question.

    Args:
        question (str): Math/quantitative question.
        model_id (str): Model used by the math specialist.

    Returns:
        str: Natural-language response from the math specialist agent.
    """
    prompt = (question or "").strip()
    if not prompt:
        return json.dumps({"error": "question is required"})
    return _ask_math_agent(prompt, model_id)


if __name__ == "__main__":
    mcp.run()
