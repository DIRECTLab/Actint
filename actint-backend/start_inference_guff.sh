#!/bin/bash

# Move to the script's directory so it can securely find .env
cd "$(dirname "$0")" || exit 1

# Load environment variables from .env file
set -a
[ -f ./.env ] && . ./.env
set +a

USERNAME=$(id -u -n)

# Check required environment variables
if [ -z "$INFERENCE_SERVER_PORT" ]; then
    echo "Error: INFERENCE_SERVER_PORT is not set. Please define it in .env" >&2
    exit 1
fi

if [ -z "$MODEL_ID" ]; then
    echo "Error: MODEL_ID is not set. Please define it in .env" >&2
    exit 1
fi

# Verify model exists
if [ ! -f "$MODEL_ID" ]; then
    echo "Error: Model file not found: $MODEL_ID" >&2
    exit 1
fi

# Optional HF_HOME check if you still want it for other tooling
if [[ -n "$HF_HOME" ]]; then
    if [[ "$HF_HOME" != /scratch/${USERNAME}/* ]]; then
        echo "Warning: HF_HOME is not in scratch storage: $HF_HOME"
    fi
fi

echo "Starting llama.cpp OpenAI-compatible inference server on port $INFERENCE_SERVER_PORT..."
echo "Model: $MODEL_ID"

llama-server \
    -m "$MODEL_ID" \
    -c "${MAX_CONTEXT_LENGTH:-132000}" \
    --host 0.0.0.0 \
    --port "$INFERENCE_SERVER_PORT" \
    -n "${MAX_NEW_TOKENS:-2000}"