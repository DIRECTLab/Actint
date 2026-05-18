def route(state):
    if state.get("done"):
        return "summarize"

    if state.get("steps", 0) >= state.get("max_steps", 5):
        return "summarize"

    if state.get("tool_request"):
        return "fetch"

    return "analyze"
