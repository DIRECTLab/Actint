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

if [ -z "$MODEL_QUANT_FORMAT" ]; then
    echo "Error: MODEL_QUANT_FORMAT is not set in .env"
    exit 1
fi

if [[ -z "$HF_HOME" ]]; then
    echo "Error: HF_HOME is not set. In .env, set HF_HOME to a directory in your scratch directory (/scratch/${USERNAME}/<your_huggingface_cache>)."
    exit 1
fi

if [[ "$HF_HOME" != /scratch/${USERNAME}/* ]]; then
    echo "Error: HF_HOME is not a scratch directory, Ryu storage may overflow. In .env, set HF_HOME to a directory in your scratch directory (/scratch/${USERNAME}/<your_huggingface_cache>)."
    exit 1
fi

echo "Starting llama.cpp OpenAI-compatible inference server on port $INFERENCE_SERVER_PORT..."
echo "Model: ${MODEL_ID}:${MODEL_QUANT_FORM}"

# To use a HuggingFace hub model directly with llama-server, you can use the -hf format
# Example: -hf bartowski/Llama-3.2-3B-Instruct-GGUF:Q8_0
# This requires a MODEL_ID containing GGUF files and a format specifier like "Q8_0"


llama-server \
    -hf "$MODEL_ID:$MODEL_QUANT_FORMAT" \
    -c ${MAX_CONTEXT_LENGTH:-132000} \
    --host 0.0.0.0 \
    --port $INFERENCE_SERVER_PORT \
    -n ${MAX_NEW_TOKENS:-2000}
