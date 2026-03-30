#!/bin/bash
# Start LLM Server

set -e

# Load environment if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set defaults
LLM_SERVER_HOST=${LLM_SERVER_HOST:-0.0.0.0}
LLM_SERVER_PORT=${LLM_SERVER_PORT:-8000}
MCP_SERVER_URL=${MCP_SERVER_URL:-http://localhost:8001}
LLM_MODEL=${LLM_MODEL:-Qwen/Qwen3.5-9B}

echo "Starting AIS Vessel Intelligence LLM Server..."
echo "  Host: $LLM_SERVER_HOST"
echo "  Port: $LLM_SERVER_PORT"
echo "  MCP Server URL: $MCP_SERVER_URL"
echo "  LLM Model: $LLM_MODEL"

# Run the LLM server
cd "$(dirname "$0")"
python -m uvicorn actint.mcp.llm_server:app \
    --host "$LLM_SERVER_HOST" \
    --port "$LLM_SERVER_PORT" \
    --reload
