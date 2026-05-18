from typing import TypedDict, Optional, List


class ADSBAgentState(TypedDict, total=False):
    user_query: str

    agent_thinking: List[str]

    tool_request: Optional[dict]
    tool_result: Optional[str]
    tool_result_structured: Optional[dict]
    tool_history: List[dict]

    steps: int
    max_steps: int
    done: bool

    final_answer: Optional[str]
