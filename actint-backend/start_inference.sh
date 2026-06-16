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

echo "Starting llama.cpp OpenAI-compatible inference server on port $INFERENCE_SERVER_PORT..."

# If MODEL_PATH is not set, check for MODEL_ID and MODEL_QUANT_FORMAT
if [[ -z "$MODEL_ID" && -z "$MODEL_PATH" ]]; then
    echo "Error: either MODEL_ID or MODEL_PATH must be set. Please define one of them in .env" >&2
    exit 1
fi

if [[ -z "$MODEL_QUANT_FORMAT" && -z "$MODEL_PATH" ]]; then
    echo "Error: MODEL_QUANT_FORMAT is not set in .env"
    exit 1
fi

if [[ -z "$HF_HOME" && -z "$MODEL_PATH" ]]; then
    echo "Error: HF_HOME is not set. In .env, set HF_HOME to a directory in your scratch directory (/scratch/${USERNAME}/<your_huggingface_cache>)."
    exit 1
fi

if [[ "$HF_HOME" != /scratch/* && -z "$MODEL_PATH" ]]; then
    echo -e "\033[33mWarning: HF_HOME (\033[1;33m${HF_HOME}\033[0;33m) is not a scratch directory, Ryu storage may overflow. In .env, set HF_HOME to a directory in your scratch directory (/scratch/${USERNAME}/<your_huggingface_cache>).\033[0m"
fi

# If MODEL_PATH is set, use that instead of MODEL_ID
if [ -n "$MODEL_PATH" ]; then
    MODEL_SPECIFIER="-m ${MODEL_PATH}"
    echo "Model: ${MODEL_PATH}"
else
    MODEL_SPECIFIER="-hf $MODEL_ID:$MODEL_QUANT_FORMAT"
    echo "Model: ${MODEL_ID}:${MODEL_QUANT_FORMAT}"
fi


llama-server \
    $MODEL_SPECIFIER \
    -c ${MAX_CONTEXT_LENGTH:-132000} \
    --host 0.0.0.0 \
    --port $INFERENCE_SERVER_PORT \
    --api-key "${MODEL_API_KEY}" \
    -n ${MAX_NEW_TOKENS:-2000}
