# from backend.langgraph.agents.ais.graph import app as ais_app

# async def run_ais(state):
#     result = await ais_app.ainvoke(
#         {
#             "user_query": state["user_query"],
#             "messages": state.get("messages", []),
#         }
#     )
#     return {"ais_result": result.get("final_answer", str(result))}

async def run_ais(state):
    return {"ais_result": "AIS Currently Not Implemented"}