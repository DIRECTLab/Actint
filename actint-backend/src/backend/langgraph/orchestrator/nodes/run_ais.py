from backend.langgraph.agents.ais.graph import app as ais_app


async def run_ais(state):
    # Initialize AIS agent state
    ais_state = {
        "user_query": state.get("user_query"),
        "agent_thinking": [],
        "tool_history": [],
        "steps": 0,
        "max_steps": 6,
        "done": False,
    }

    result = await ais_app.ainvoke(ais_state)

    return {"ais_result": result.get("final_answer", str(result))}
