# AIS Vessel Intelligence MCP System

A self-contained Model Context Protocol (MCP) system that provides AI-powered natural language querying of AIS (Automatic Identification System) vessel data.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│ User Application / Browser                                  │
└─────────────────┬──────────────────────────────────────────┘
                  │ HTTP /query
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI LLM Server (Port 8000)                              │
│ - Qwen/Qwen3.5-9B Language Model                            │
│ - Natural language query processing                         │
│ - Endpoints: /query, /health, /tools                        │
└─────────────────┬──────────────────────────────────────────┘
                  │ HTTP (MCP Protocol)
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ MCP Server (Port 8001)                                      │
│ - Vessel location queries                                   │
│ - Geographic context tools                                  │
│ - Fleet analysis                                            │
│ - Destination prediction                                    │
└─────────────────┬──────────────────────────────────────────┘
                  │ Python API
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ AIS Database & Tools                                        │
│ - query_database.py (connection to AIS data)                │
│ - previous_locations.py                                     │
│ - lat_lon_context.py                                        │
│ - close_to_fleet.py                                         │
│ - ship_going.py                                             │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
cd actint/src/actint/mcp/
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and customize:

```bash
cp .env.example .env
# Edit .env with your settings
```

Key environment variables:
- `LLM_MODEL`: LLM to use (default: Qwen/Qwen3.5-9B)
- `MCP_SERVER_URL`: URL where MCP server will run
- `DATABASE_URL`: Connection to your AIS database

## Running the System

### Option 1: Start Both Servers Manually

Terminal 1 - Start MCP Server:
```bash
bash start_mcp_server.sh
# Output: AIS Vessel Intelligence MCP Server running...
```

Terminal 2 - Start LLM Server:
```bash
bash start_llm_server.sh
# Output: Uvicorn running on http://0.0.0.0:8000
```

### Option 2: Using Docker Compose

```bash
docker-compose up
```

## Usage

### Query Endpoint

Make a POST request to `/query`:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is USS KIDD right now?",
    "max_tokens": 256,
    "temperature": 0.7
  }'
```

Response:
```json
{
  "question": "Where is USS KIDD right now?",
  "answer": "USS KIDD is currently positioned at coordinates...",
  "tools_used": ["get_vessel_current_position", "get_location_context"],
  "execution_time_seconds": 2.45,
  "timestamp": "2026-03-30T10:15:32.123456"
}
```

### Available Tools

The MCP server exposes the following tools:

#### Vessel Queries
- `get_vessel_locations` - Get all recorded positions for a vessel (MMSI)
- `get_vessel_current_position` - Get most recent position
- `ship_following_analysis` - Check if one vessel follows another's path

#### Geographic Context
- `get_location_context` - Get maritime region, nearest ports, waterways
- `get_distance_between` - Calculate distance between two coordinates
- `identify_maritime_region` - Identify which sea/ocean a location is in
- `find_nearest_port` - Find nearest major port to coordinates
- `find_nearest_waterway` - Find nearest strategic waterway

#### Fleet Analysis
- `calculate_fleet_position` - Get average position of a fleet
- `is_ship_in_fleet` - Check if a vessel is within fleet proximity

#### Destination Prediction
- `get_vessel_destination` - Predict where a vessel is heading

### Health Check

```bash
curl "http://localhost:8000/health"
```

Response:
```json
{
  "status": "healthy",
  "llm_loaded": true,
  "mcp_reachable": true,
  "timestamp": "2026-03-30T10:15:32.123456"
}
```

### List Available Tools

```bash
curl "http://localhost:8000/tools"
```

### Call a Specific Tool

```bash
curl -X POST "http://localhost:8000/tools/get_vessel_current_position" \
  -H "Content-Type: application/json" \
  -d '{"mmsi": 368011000}'
```

## Example Queries

```
"Where is USS KIDD?"
"What vessels are near San Diego?"
"Is USS MONTGOMERY close to Pearl Harbor?"
"What ships are in the 7th Fleet fleet?"
"Which maritime region is this location in: 35.2, 139.66?"
"How far is the vessel at 32.71, -117.16 from the nearest port?"
"Where is vessel with MMSI 368011000 heading?"
"Have these two ships been following similar paths?"
```

## Development

### Project Structure

```
mcp/
├── mcp_server.py           # MCP protocol server (tool definitions & execution)
├── llm_server.py           # FastAPI LLM server (query endpoint)
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment configuration
├── start_mcp_server.sh     # Script to start MCP server
├── start_llm_server.sh     # Script to start LLM server
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Docker image for deployment
└── README.md               # This file
```

### Adding New Tools

To add a new tool to the MCP server:

1. Import the tool function in `mcp_server.py`
2. Add a tool definition in `handle_list_tools()`
3. Add a handler in `handle_call_tool()`

Example:
```python
# In handle_list_tools()
types.Tool(
    name="new_tool",
    description="Description of what the tool does",
    inputSchema={...}
),

# In handle_call_tool()
elif name == "new_tool":
    result = my_tool_function(arguments["param"])
    return [types.TextContent(type="text", text=json.dumps(result))]
```

### Modifying the LLM

Change the `LLM_MODEL` environment variable to use a different model:

```bash
export LLM_MODEL="mistralai/Mistral-7B-v0.1"
bash start_llm_server.sh
```

Supported models:
- `Qwen/Qwen3.5-9B` (recommended)
- `Qwen/Qwen2-7B`
- `mistralai/Mistral-7B-v0.1`

## Troubleshooting

### MCP Server Not Starting

- Check port 8001 is not in use: `lsof -i :8001`
- Verify database connection is working
- Check logs for import errors

### LLM Server Can't Connect to MCP

- Verify MCP server is running: `curl http://localhost:8001/health`
- Check `MCP_SERVER_URL` environment variable
- Firewalls may be blocking communication

### Out of Memory During Model Loading

- Use a smaller model: `export LLM_MODEL="Qwen/Qwen2-7B"`
- Run on GPU device: `export LLM_DEVICE=cuda`
- Reduce `max_tokens` in queries

### Slow Queries

- Reduce `max_tokens` parameter
- Increase `temperature` for faster but less accurate responses
- Consider using ONNX quantized models for inference

## Performance Tuning

### For Production

```bash
# Use multiple workers
export WORKERS=4

# Increase request timeout
export REQUEST_TIMEOUT=120

# Use GPU acceleration
export LLM_DEVICE=cuda

# Log level
export LOG_LEVEL=WARNING
```

### Memory Optimization

```bash
# Use float16 precision (automatic with CUDA)
export TORCH_DTYPE=float16

# Enable model quantization
export QUANTIZE_MODEL=true
```

## License

This system is part of the JFN Groundtruth Simulator project.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review server logs in `/tmp/ais_queries.jsonl`
3. Use `/health` endpoint to check system status
