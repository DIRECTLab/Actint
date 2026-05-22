#!/bin/bash

# Move to the script's directory so it can securely find .env
cd "$(dirname "$0")" || exit 1

# Load environment variables from .env file
set -a
[ -f ./.env ] && . ./.env
set +a

# Port to run the inference server on
PORT=${INFERENCE_SERVER_PORT}
# Model ID to serve
MODEL_ID=${MODEL_ID}

echo "Starting vLLM OpenAI-compatible inference server on port $PORT..."
echo "Model: $MODEL_ID"

EXTRA_ARGS=""
if [ "$MODEL_ID" = "google/gemma-4-31B-it" ]; then
    echo "Setting max-model-len to 131392 for $MODEL_ID"
    EXTRA_ARGS="--max-model-len 131392 --enable-auto-tool-choice --tool-call-parser gemma4 --dtype bfloat16"
elif [[ "$MODEL_ID" =~ [Qq]wen3 ]]; then
    echo "Setting tool-call-parser for Qwen3 model"
    EXTRA_ARGS="--enable-auto-tool-choice --tool-call-parser hermes" # or use qwen25 / hermes based on your vLLM version
fi

# Start the vllm server
vllm serve "$MODEL_ID" $EXTRA_ARGS --port $PORT
