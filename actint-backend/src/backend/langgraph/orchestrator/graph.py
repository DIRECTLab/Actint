from langgraph.graph import StateGraph, START, END

from .state import OrchestratorState
from .nodes.route_task import route_task
from .nodes.run_ais import run_ais
from .nodes.run_adsb import run_adsb
from .nodes.merge_results import merge_results
from .nodes.final_response import final_response


def route_from_task(state: OrchestratorState):
    route = state.get("route")

    if route == "ais":
        return "run_ais"
    if route == "adsb":
        return "run_adsb"
    if route == "both":
        return "run_ais"

    return "final_response"


def after_ais(state: OrchestratorState):
    return "run_adsb" if state.get("route") == "both" else "merge_results"


builder = StateGraph(OrchestratorState)

builder.add_node("route_task", route_task)
builder.add_node("run_ais", run_ais)
builder.add_node("run_adsb", run_adsb)
builder.add_node("merge_results", merge_results)
builder.add_node("final_response", final_response)

builder.add_edge(START, "route_task")

builder.add_conditional_edges(
    "route_task",
    route_from_task,
    {
        "run_ais": "run_ais",
        "run_adsb": "run_adsb",
        "final_response": "final_response",
    },
)

builder.add_conditional_edges(
    "run_ais",
    after_ais,
    {
        "run_adsb": "run_adsb",
        "merge_results": "merge_results",
    },
)

builder.add_edge("run_adsb", "merge_results")
builder.add_edge("merge_results", END)
builder.add_edge("final_response", END)

app = builder.compile()