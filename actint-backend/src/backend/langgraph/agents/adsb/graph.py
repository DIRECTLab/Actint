from langgraph.graph import StateGraph, START, END

from .state import ADSBAgentState
from .nodes.analyze import analyze
from .nodes.fetch import fetch_information
from .nodes.summarize import summarize_reasoning
from .nodes.router import route


def build_graph():
    builder = StateGraph(ADSBAgentState)

    builder.add_node("analyze", analyze)
    builder.add_node("fetch", fetch_information)
    builder.add_node("summarize", summarize_reasoning)

    builder.add_edge(START, "analyze")

    builder.add_conditional_edges(
        "analyze",
        route,
        {
            "fetch": "fetch",
            "analyze": "analyze",
            "summarize": "summarize",
        },
    )

    builder.add_edge("fetch", "analyze")
    builder.add_edge("summarize", END)

    return builder.compile()


app = build_graph()
