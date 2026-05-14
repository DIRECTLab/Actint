from __future__ import annotations

from typing import Any, Optional, TypedDict

from .graph import app


class OrchestratorRequest(TypedDict, total=False):
    user_query: str
    messages: list[dict[str, Any]]
    metadata: dict[str, Any]


class OrchestratorResponse(TypedDict, total=False):
    route: str
    ais_result: Optional[str]
    adsb_result: Optional[str]
    final_answer: str
    messages: list[dict[str, Any]]


def build_orchestrator_state(
    user_query: str,
    messages: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "user_query": user_query,
        "messages": messages or [],
    }

    if metadata:
        state["metadata"] = metadata

    return state


async def run_orchestrator(
    user_query: str,
    messages: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> OrchestratorResponse:
    state = build_orchestrator_state(
        user_query=user_query,
        messages=messages,
        metadata=metadata,
    )

    result = await app.ainvoke(state)

    return {
        "route": result.get("route", "unknown"),
        "ais_result": result.get("ais_result"),
        "adsb_result": result.get("adsb_result"),
        "final_answer": result.get("final_answer", ""),
        "messages": result.get("messages", messages or []),
    }


def run_orchestrator_sync(
    user_query: str,
    messages: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> OrchestratorResponse:
    state = build_orchestrator_state(
        user_query=user_query,
        messages=messages,
        metadata=metadata,
    )

    result = app.invoke(state)

    return {
        "route": result.get("route", "unknown"),
        "ais_result": result.get("ais_result"),
        "adsb_result": result.get("adsb_result"),
        "final_answer": result.get("final_answer", ""),
        "messages": result.get("messages", messages or []),
    }