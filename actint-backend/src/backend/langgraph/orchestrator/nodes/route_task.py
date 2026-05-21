from backend.langgraph.common.llm.inference import generate
from backend.langgraph.common.llm.model import tokenizer

async def route_task(state):
    query = state["user_query"]

    prompt = f"""
You are a strict routing classifier. Your only job is to choose exactly one
label for the user's request.

Classify the request into one of these labels:
- ais
- adsb
- both
- final_response

Definitions:
- ais: Use this when the request should be handled by the AIS agent,
  meaning it asks for maritime vessel data, ship positions, port activity,
  vessel tracking, or anything specifically related to AIS.
- adsb: Use this when the request should be handled by the ADS-B agent,
  meaning it asks for aircraft data, flight tracking, aircraft positions,
  air traffic, or anything specifically related to ADS-B.
- both: Use this when the request clearly requires both AIS and ADS-B data
  or a combined answer from both agents.
- final_response: Use this when the request does not require AIS or ADS-B
  data and can be answered directly by the assistant. This includes general
  knowledge, casual conversation, writing help, coding help, math, and any
  other unrelated question. If the question is unrelated to AIS/ADS-B data,
  always choose final_response.

Routing rules:
- If the request is about AIS data, choose ais.
- If the request is about ADS-B data, choose adsb.
- If the request requires both datasets, choose both.
- If the request is unrelated to AIS or ADS-B, choose final_response.
- If you cannot confidently decide, choose unknown.

Examples:
- "What is the capital of France?" -> final_response
- "How are you?" -> final_response
- "Show me ships near Singapore." -> ais
- "Track this aircraft." -> adsb
- "Compare nearby ships and aircraft activity." -> both
- "Find the vessel with this incomplete identifier." -> unknown

Response Rules:
- Do not repeat yourself
- Do not use markdown
- Do not add extra text
- Only respond in plain text, no code, markdown formatting, or formatting. Just return the label as a plain text response.
- Be consise, do not write any explainations, just return the label.
- End your response immediately after the label use the following text: </final>
- Return only the label. Do not explain your answer.

Example Response:
final_response</final>

User query:
{query}

Return only the label. Do not explain your answer.
"""

    route = (await generate(prompt, max_tokens=15)).strip().lower()

    if "ais" in route:
        print('CALLING AIS')
        route = "ais"
    elif "adsb" in route:
        print('CALLING ADSB')
        route = "adsb"
    elif "both" in route:
        print('CALLING BOTH')
        route = "both"
    elif "final_response" in route:
        route = "final_response"
    else:
        route = "unknown"

    return {"route": route}