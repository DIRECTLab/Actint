# Quick Start Guide

## 5-Minute Setup

### Prerequisites
- Python 3.10+
- 8GB+ RAM (16GB+ recommended for LLM)
- GPU recommended but not required

### Step 1: Install

```bash
cd actint/src/actint/mcp/
pip install -r requirements.txt
```

### Step 2: Configure

```bash
cp .env.example .env
# Optionally edit .env to change ports, models, etc.
```

### Step 3: Run MCP Server (Terminal 1)

```bash
bash start_mcp_server.sh
```

You should see:
```
AIS Vessel Intelligence MCP Server running...
Available tools:
  - get_vessel_locations: Get all recorded positions...
  ...
```

### Step 4: Run LLM Server (Terminal 2)

```bash
bash start_llm_server.sh
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 5: Test It

In a third terminal:

```bash
python example_client.py
```

Or use curl:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "Where is USS KIDD?"}'
```

## Common Issues & Solutions

### "ModuleNotFoundError: No module named 'actint'"

Run from the correct directory:
```bash
cd /path/to/JFN-Groundtruth-Simulator/actint/src/actint/mcp/
```

Or ensure actint is installed:
```bash
cd /path/to/JFN-Groundtruth-Simulator/actint/
pip install -e .
```

### "Address already in use"

Port is taken. Change in `.env`:
```
MCP_PORT=8002
LLM_SERVER_PORT=8001
```

Then update MCP_SERVER_URL accordingly.

### "Timeout connecting to MCP server"

Make sure both servers are running:
```bash
# Check if ports are listening
lsof -i :8000
lsof -i :8001
```

### Model loading takes forever / Out of memory

Use a smaller model:
```bash
export LLM_MODEL="Qwen/Qwen2-7B"
bash start_llm_server.sh
```

## Next Steps

1. **Explore the API** - Check [API_REFERENCE.md](API_REFERENCE.md)
2. **Run Example Client** - `python example_client.py`
3. **Read Full README** - `cat README.md`
4. **Check Logs** - Query logs saved to `$QUERY_LOG_FILE`

## Example Queries to Try

```
"Where is USS KIDD?"
"Show me vessel 368011000"
"What's the nearest port to coordinates 35.2, 139.66?"
"Is this ship close to its fleet?"
"Where will the ship be heading?"
```

## Architecture Quick Reference

```
User/App
  ↓ HTTP /query
LLM Server (Port 8000) [Qwen LLM]
  ↓ MCP Protocol
MCP Server (Port 8001) [Tools]
  ↓ Python API
Database
```

Need help? See README.md for detailed documentation.
