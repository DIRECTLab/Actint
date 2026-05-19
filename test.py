from flask import Flask, request, jsonify
from llama_cpp import Llama
import time

app = Flask(__name__)

# ----------------------------
# Load model once (important)
# ----------------------------
llm = Llama(
    model_path="../models/gemma-4-26B-A4B-it-MXFP4_MOE_BF16.gguf",
    n_gpu_layers=-1,
    n_ctx=50000,
)

# ----------------------------
# Chat format converter
# ----------------------------
def format_messages(messages):
    """
    Converts OpenAI chat format → llama.cpp prompt string
    Safe + deterministic (no dict leaks into model)
    """

    prompt = ""

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        # Normalize role tags for instruction models
        if role == "system":
            prompt += f"<|system|>\n{content}\n"
        elif role == "user":
            prompt += f"<|user|>\n{content}\n"
        elif role == "assistant":
            prompt += f"<|assistant|>\n{content}\n"

    prompt += "<|assistant|>\n"
    return prompt


# ----------------------------
# OpenAI-compatible endpoint
# ----------------------------
@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json()

    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    prompt = format_messages(messages)

    # ----------------------------
    # llama.cpp inference
    # ----------------------------
    output = llm(
        prompt,
        max_tokens=data.get("max_tokens", 512),
        temperature=data.get("temperature", 0.7),
        top_p=data.get("top_p", 0.9),
        repeat_penalty=data.get("repeat_penalty", 1.1),
        stop=["<|user|>", "<|system|>"]
    )

    text = output["choices"][0]["text"].strip()

    # ----------------------------
    # OpenAI-style response
    # ----------------------------
    return jsonify({
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model", "local-model"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": -1,
            "completion_tokens": -1,
            "total_tokens": -1
        }
    })


# ----------------------------
# Health check endpoint
# ----------------------------
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


# ----------------------------
# Run server (HPC-safe)
# ----------------------------
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",   # IMPORTANT: no network exposure
        port=8000,
        debug=False
    )