# API Reference

## LLM Server Endpoints

### POST /query

Query the vessel intelligence system with natural language.

**Request:**
```json
{
  "question": "Where is USS KIDD?",
  "max_tokens": 256,
  "temperature": 0.7
}
```

**Parameters:**
- `question` (string, required): Natural language question about vessels
- `max_tokens` (integer, optional): Maximum tokens to generate (default: 256)
- `temperature` (float, optional): Sampling temperature 0.0-1.0 (default: 0.7)

**Response:**
```json
{
  "question": "Where is USS KIDD?",
  "answer": "USS KIDD is currently...",
  "tools_used": ["get_vessel_current_position", "get_location_context"],
  "execution_time_seconds": 2.45,
  "timestamp": "2026-03-30T10:15:32.123456"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request (empty question)
- `500` - Server error

---

### GET /health

Check system health and connectivity.

**Response:**
```json
{
  "status": "healthy",
  "llm_loaded": true,
  "mcp_reachable": true,
  "timestamp": "2026-03-30T10:15:32.123456"
}
```

**Status:** `healthy` or `degraded`

---

### GET /tools

List all available MCP tools.

**Response:**
```json
{
  "tools": [
    {
      "name": "get_vessel_locations",
      "description": "Get all recorded positions for a specific vessel",
      "inputSchema": {...}
    },
    ...
  ]
}
```

---

### POST /tools/{tool_name}

Call a specific MCP tool directly.

**URL Parameters:**
- `tool_name` (string): Name of the tool to call

**Request Body:**
Tool-specific arguments (varies by tool)

**Response:**
```json
{
  "result": {...}
}
```

---

## MCP Tools

### Vessel Location Queries

#### get_vessel_locations

Get all recorded positions for a vessel.

**Input:**
```json
{
  "mmsi": 368011000
}
```

**Output:**
```json
[
  {
    "mmsi": 368011000,
    "vessel_name": "USS KIDD",
    "timestamp": "2026-03-30T10:15:32.123456",
    "latitude": 35.2,
    "longitude": 139.66,
    "speed_over_ground": 12.5,
    "course_over_ground": 045.0,
    "heading": 043.0
  },
  ...
]
```

---

#### get_vessel_current_position

Get the most recent position of a vessel.

**Input:**
```json
{
  "mmsi": 368011000
}
```

**Output:**
```json
{
  "mmsi": 368011000,
  "vessel_name": "USS KIDD",
  "timestamp": "2026-03-30T10:15:32.123456",
  "latitude": 35.2,
  "longitude": 139.66,
  "speed_over_ground": 12.5,
  "course_over_ground": 045.0,
  "heading": 043.0
}
```

---

#### ship_following_analysis

Determine if one vessel has been following another.

**Input:**
```json
{
  "mmsi1": 368011000,
  "mmsi2": 368011001
}
```

**Output:**
```
Vessel 368011001 (name) went to the same area as 368011000 (name) within 1:00:00 of when 368011000 was there 5/10 times.
```

---

### Geographic Context

#### get_location_context

Get geographic context for coordinates.

**Input:**
```json
{
  "latitude": 35.2,
  "longitude": 139.66
}
```

**Output:**
```json
{
  "latitude": 35.2,
  "longitude": 139.66,
  "maritime_region": "Philippine Sea",
  "nearest_port": {
    "name": "Yokosuka, Japan",
    "distance_nm": 125.3
  },
  "nearest_waterway": {
    "name": "Luzon Strait",
    "distance_nm": 289.5
  },
  "reverse_geocoding": "Izu Peninsula, Japan"
}
```

---

#### get_distance_between

Calculate distance and bearing between coordinates.

**Input:**
```json
{
  "lat1": 32.7157,
  "lon1": -117.1611,
  "lat2": 33.7405,
  "lon2": -118.2675
}
```

**Output:**
```json
{
  "distance_nm": 65.4,
  "bearing_degrees": 327.5,
  "cardinal_direction": "NW"
}
```

---

#### identify_maritime_region

Identify maritime region for coordinates.

**Input:**
```json
{
  "latitude": 35.0,
  "longitude": 140.0
}
```

**Output:**
```json
{
  "region": "Philippine Sea"
}
```

---

#### find_nearest_port

Find nearest major port to coordinates.

**Input:**
```json
{
  "latitude": 32.7157,
  "longitude": -117.1611
}
```

**Output:**
```json
{
  "port_name": "San Diego, CA",
  "distance_nm": 2.5
}
```

---

#### find_nearest_waterway

Find nearest strategic waterway to coordinates.

**Input:**
```json
{
  "latitude": 35.2,
  "longitude": 119.5
}
```

**Output:**
```json
{
  "waterway_name": "Taiwan Strait",
  "distance_nm": 125.0
}
```

---

### Fleet Analysis

#### calculate_fleet_position

Calculate average position of a fleet.

**Input:**
```json
{
  "fleet_name": "7th Fleet"
}
```

**Output:**
```json
{
  "fleet_name": "7th Fleet",
  "fleet_position": {
    "latitude": 34.5,
    "longitude": 139.2
  }
}
```

---

#### is_ship_in_fleet

Check if vessel is within fleet proximity (10 NM).

**Input:**
```json
{
  "mmsi": 368011000
}
```

**Output:**
```
This ship is in the fleet (Within 10.0 NM of the fleet)
```

or

```
This ship is not in the fleet (More than 10.0 NM from the fleet)
```

---

### Destination Prediction

#### get_vessel_destination

Predict where a vessel is heading.

**Input:**
```json
{
  "mmsi": 368011000,
  "number_detections": 300
}
```

**Output:**
```json
{
  "mmsi": 368011000,
  "note": "Destination analysis completed. See server logs for trajectory analysis."
}
```

---

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad request (invalid parameters)
- `404` - Not found (invalid tool name)
- `500` - Server error
- `503` - Service unavailable (MCP server down)

---

## Rate Limiting & Timeouts

- Request timeout: 60 seconds (configurable via `REQUEST_TIMEOUT`)
- No rate limiting in default configuration
- LLM inference: typically 2-10 seconds per query

---

## Usage Examples

### Python

```python
import httpx

client = httpx.Client()

# Query endpoint
response = client.post(
    "http://localhost:8000/query",
    json={
        "question": "Where is USS KIDD?",
        "max_tokens": 256,
        "temperature": 0.7
    }
)

print(response.json()["answer"])
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    question: 'Where is USS KIDD?',
    max_tokens: 256,
    temperature: 0.7
  })
});

const data = await response.json();
console.log(data.answer);
```

### curl

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is USS KIDD?",
    "max_tokens": 256,
    "temperature": 0.7
  }'
```

---

## See Also

- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - Quick setup guide
- [example_client.py](example_client.py) - Python client example
