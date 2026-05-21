from backend.langgraph.common.llm.inference import generate
from backend.langgraph.common.llm.model import tokenizer

async def final_response(state):
    prompt = f"""
You are the final response generator.

Write exactly one short response to the user.
Rules:
- Be concise
- Do not repeat yourself
- Do not use markdown
- Do not add extra text
- End your response immediately after the answer use the following text: </final>

Example User Query:
How are you doing today?
ExampleResponse:
I'm doing well, thank you!</final>

User query:
{state["user_query"]}

Response:
"""
    final_answer = await generate(prompt, max_tokens=10000)
    return {"final_answer": final_answer}