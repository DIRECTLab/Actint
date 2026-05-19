import os
from fastapi import FastAPI, Request
from llama_cpp import Llama
import uvicorn

# 1. Force absolute offline environment containment
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

app = FastAPI()

print("Loading model into RTX 5090 VRAM...")
llm = Llama(
    #model_path=os.path.expanduser("/scratch/daxtonb/qwen_gguf/Qwen3.5-122B-A10B-Q4_K_M-00001-of-00002.gguf"),
    #model_path=os.path.expanduser("/home/daxtonb/models/gemma/gemma-4-26B-A4B-it-MXFP4_MOE_BF16.gguf"),
    model_path=os.path.expanduser("/scratch/daxtonb/chat_gpt/gpt-oss-120b-UD-Q8_K_XL-00001-of-00002.gguf"),
    n_gpu_layers=-1, # Force all layers to GPU
    n_ctx=131072,      # Context window size
    verbose=False    # Suppresses internal engine chat log spam
)
print("Model loaded successfully!")

# @app.post("/v1/chat/completions")
# async def chat_completions(request: Request):
#     body = await request.json()
    
#     # Extract OpenAI parameters from the inbound client request
#     messages = body.get("messages", [])
#     max_tokens = body.get("max_tokens", 512)
#     temperature = body.get("temperature", 0.7)
#     stream = body.get("stream", False)
    
#     # 2. Use the native OpenAI v1 formatter inside llama_cpp.
#     # This automatically builds an identical JSON schema and tracks actual token tracking lengths.
#     response = llm.create_chat_completion_openai_v1(
#         messages=messages,
#         max_tokens=max_tokens,
#         temperature=temperature,
#         stream=stream
#     )
    
#     return response




@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    messages = body.get("messages", [])
    max_tokens = body.get("max_tokens", 512)
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)

    # 🔧 FIX: normalize OpenAI multimodal -> plain text
    def normalize_messages(msgs):
        fixed = []

        for m in msgs:
            content = m.get("content", "")

            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                content = "\n".join(parts)

            # 🔥 REMOVE QWEN CHANNEL TOKENS
            content = strip_qwen_channels(content)

            fixed.append({
                "role": m["role"],
                "content": content
            })

        return fixed

    messages = normalize_messages(messages)

    response = llm.create_chat_completion_openai_v1(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=stream
    )

    return response

import re

def strip_qwen_channels(text: str) -> str:
    if not isinstance(text, str):
        return ""

    # remove Qwen channel markers
    text = re.sub(r"<\|channel\|>", "", text)
    text = re.sub(r"<\|message\|>", "", text)
    text = re.sub(r"<\|end\|>", "", text)

    return text.strip()





if __name__ == "__main__":
    # Force direct loopback targeting to bypass DNS name resolution entirely
    uvicorn.run(app, host="127.0.0.1", port=8000)