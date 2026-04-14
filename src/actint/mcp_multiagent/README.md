# AIS Vessel Intelligence MCP Multi-Agent System

A self-contained Model Context Protocol (MCP) system that provides AI-powered natural language querying of AIS (Automatic Identification System) vessel data.

## Multi-Agent Design

This folder now includes a two-agent setup in `smolagent.py`:

- `reasoning_agent`: manager agent that reasons over evidence and asks follow-up questions
- `sql_agent`: specialist agent that can only use SQL MCP tools (`get_database_info`, `query_database`)

Interaction flow:

1. User asks a natural-language question.
2. `reasoning_agent` delegates data retrieval questions to `sql_agent`.
3. `sql_agent` runs read-only SQL against AIS SQLite and returns natural-language findings.
4. `reasoning_agent` synthesizes the final answer.

## Installation

### 1. Create env andInstall Dependencies

```bash
conda create -n actint_env python=3.12 -y
conda activate actint_env
pip install -e ./actint
pip install -r ./actint/requirements.txt
```

### 2. Configuration

Copy the example environment file and customize:

```bash
cp ./actint/src/actint/mcp/.env.example ./actint/src/actint/mcp/.env
# Edit .env with your settings
```

Key environment variables:
- `LLM_MODEL`: LLM to use (default: Qwen/Qwen3.5-9B)
- `MCP_SERVER_URL`: URL where MCP server will run
- `DATABASE_URL`: Connection to your AIS database

## Running the System

### Option 0: Run the Multi-Agent CLI

From repository root:

```bash
python src/actint/mcp_multiagent/smolagent.py "Where is the USS Montgomery currently heading?"
```

If no question is supplied, a default prompt is used.

### Option 1: Start Server


```bash
python ./actint/src/actint/mcp/llm_server.py
# Output: Uvicorn running on http://0.0.0.0:8000
```
## Usage
### Query Endpoint
Make a POST request to `/query`:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is USS KIDD right now?"
  }'
```

If you want to see live chunked output (including tool-call markup and tool results)

```bash
curl -N -X POST "http://localhost:8000/query_stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "question": "Where is USS KIDD right now?"
  }'
```

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
```

Supported models:
- `Qwen/Qwen3.5-9B` (recommended)
- `Qwen/Qwen2-7B`
- `mistralai/Mistral-7B-v0.1`

