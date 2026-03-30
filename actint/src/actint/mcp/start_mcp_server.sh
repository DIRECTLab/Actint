#!/bin/bash
# Start MCP Server

set -e

# Load environment if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set defaults
MCP_HOST=${MCP_HOST:-0.0.0.0}
MCP_PORT=${MCP_PORT:-8001}
LOG_LEVEL=${LOG_LEVEL:-INFO}

echo "Starting AIS Vessel Intelligence MCP Server..."
echo "  Host: $MCP_HOST"
echo "  Port: $MCP_PORT"
echo "  Log Level: $LOG_LEVEL"

# Run the MCP server
python -m actint.mcp.mcp_server
