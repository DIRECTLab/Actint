from typing import TypedDict, Optional, Literal, List

class AISAgentState(TypedDict, total=False):
    user_query: str
    agent_thinking: Optional[str]
    route: Literal["ais", "adsb", "both", "unknown", "final_response"]
    ais_result: Optional[str]
    adsb_result: Optional[str]
    final_answer: Optional[str]
    messages: List[dict]