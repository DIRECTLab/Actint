import os
import sys
import io
import re
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from mcp import StdioServerParameters
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from phoenix.otel import register
from smolagents import MCPClient, ToolCallingAgent, TransformersModel

from actint.mcp_multiagent import mcp_server_reasoning

register(project_name="actint")
SmolagentsInstrumentor().instrument()

DEFAULT_MODEL_ID = "Qwen/Qwen3.5-9B"
DEFAULT_QUESTION = "Where is the USS Montgomery?"
REASONING_LOG_PATH = Path(os.getcwd()) / "reasoning_agent.log"
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
OTEL_NOISE_MARKERS = (
    "Transient error StatusCode.UNAVAILABLE encountered while exporting traces",
    "Failed to export traces to localhost:4317",
)


def _clean_log_text(text: str) -> str:
    """Make verbose agent logs easier to read as plain text."""
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


def _resolve_python_executable() -> str:
    """Resolve Python executable for launching the MCP stdio server."""
    conda_prefix = os.getenv("CONDA_PREFIX")
    if conda_prefix:
        candidate = Path(conda_prefix) / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _load_reasoning_template() -> str:
    template_path = Path(__file__).with_name("qwen_system_prompt_reasoning.jinja")
    return template_path.read_text(encoding="utf-8")


def _prompt_for_question() -> str:
    """Prompt user for a question, with 'default' shortcut support."""
    print("Enter your question for the multi-agent system.")
    print("Type 'default' to use the built-in test question. which is '" + DEFAULT_QUESTION + "'")
    user_input = input("Question: ").strip()
    if not user_input or user_input.lower() == "default":
        return DEFAULT_QUESTION
    return user_input


def _build_reasoning_agent(
    model: TransformersModel,
    reasoning_tools: list,
) -> ToolCallingAgent:
    return ToolCallingAgent(
        tools=reasoning_tools,
        model=model,
        name="reasoning_agent",
        verbosity_level=2,
        description=(
            "Reasoning manager agent. It should synthesize answers from ask_sql_specialist and "
            "ask_map_specialist and ask_math_specialist, "
            "ask follow-up questions when needed, and provide the final response."
        ),
    )


def run_multi_agent(question: str = DEFAULT_QUESTION, model_id: str = DEFAULT_MODEL_ID) -> str:
    python = _resolve_python_executable()
    reasoning_server_params = StdioServerParameters(
        command=python,
        args=[mcp_server_reasoning.__file__],
        env=os.environ.copy(),
        cwd=os.getcwd(),
    )

    reasoning_mcp_client = None
    try:
        reasoning_mcp_client = MCPClient(reasoning_server_params, structured_output=False)
        reasoning_tools = [
            tool
            for tool in reasoning_mcp_client.get_tools()
            if getattr(tool, "name", "")
            in {
                "ask_sql_specialist",
                "ask_map_specialist",
                "ask_math_specialist",
                "get_reasoning_contract",
                "health",
            }
        ]

        model = TransformersModel(model_id=model_id)
        reasoning_agent = _build_reasoning_agent(
            model=model,
            reasoning_tools=reasoning_tools,
        )

        if "Qwen3.5" in model_id:
            reasoning_template = _load_reasoning_template()
            reasoning_agent.prompt_templates["system_prompt"] = (
                reasoning_template
                + "\n\nYou are the reasoning manager agent. You do not query data tools directly. "
                "Delegate SQL/data retrieval by calling ask_sql_specialist and maritime geospatial retrieval "
                "by calling ask_map_specialist and quantitative computation by calling ask_math_specialist, "
                "ask follow-up questions when needed, "
                "and synthesize a final answer."
            )

        reasoning_trace = io.StringIO()
        with redirect_stdout(reasoning_trace), redirect_stderr(reasoning_trace):
            result = reasoning_agent.run(question)
        REASONING_LOG_PATH.write_text(
            _clean_log_text(reasoning_trace.getvalue()),
            encoding="utf-8",
        )
        return str(result)
    finally:
        if reasoning_mcp_client is not None:
            reasoning_mcp_client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_input = " ".join(sys.argv[1:]).strip()
        user_question = DEFAULT_QUESTION if cli_input.lower() == "default" else cli_input
        if not user_question:
            user_question = DEFAULT_QUESTION
    else:
        user_question = _prompt_for_question()

    output = run_multi_agent(question=user_question, model_id=DEFAULT_MODEL_ID)
    print(output)