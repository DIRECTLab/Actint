"""
FastAPI LLM Server for AIS Vessel Intelligence.

Hosts a Qwen LLM that uses MCP tools to answer questions about
vessel positions, locations, and maritime activities.

The server:
1. Receives natural language queries via /query endpoint
2. Determines which MCP tools are needed
3. Calls the standalone MCP server to get tool results
4. Uses the LLM to generate natural language responses
"""

import os
import json
import logging
import re
import asyncio
import threading
import queue
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
from actint.data_processing.json_to_db import main, SQLITE_PATH

# Import MCP tools directly from mcp_server
from actint.mcp.mcp_server import (
    get_vessel_locations,
    get_vessel_current_position,
    ship_following_analysis,
    get_location_context,
    get_distance_between,
    identify_maritime_region,
    find_nearest_port,
    find_nearest_waterway,
    calculate_fleet_position,
    is_ship_in_fleet,
    get_vessel_destination,
    get_database_info,
    query_database,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration from Environment
# ============================================================================

LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-9B")
LLM_DEVICE = os.getenv("LLM_DEVICE", "auto")
QUERY_LOG_FILE = os.getenv("QUERY_LOG_FILE", "/tmp/ais_queries.jsonl")

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="AIS Vessel Intelligence LLM",
    description="Query AIS vessel data using natural language",
    version="1.0.0"
)

# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for vessel queries."""
    question: str
    max_tokens: int = 100_000
    temperature: float = 1.0


class QueryResponse(BaseModel):
    """Response model for vessel queries."""
    question: str
    answer: str
    tools_used: list[str]
    execution_time_seconds: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    llm_loaded: bool
    mcp_reachable: bool
    timestamp: str


# ============================================================================
# LLM Manager
# ============================================================================

class LLMManager:
    """Manages LLM loading and inference."""
    
    def __init__(self, model_name: str = LLM_MODEL):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self.is_loaded = False
        logger.info(f"Initializing LLMManager with model: {model_name}")
    
    @property
    def tokenizer(self):
        """Get tokenizer, loading if necessary."""
        if self._tokenizer is None:
            self.load_model()
        return self._tokenizer
    
    @property
    def model(self):
        """Get model, loading if necessary."""
        if self._model is None:
            self.load_model()
        return self._model
    
    def load_model(self):
        """Load the LLM model and tokenizer."""
        if self.is_loaded:
            return
        
        try:
            logger.info(f"Loading model: {self.model_name}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            device_map = LLM_DEVICE if torch.cuda.is_available() else None
            
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch_dtype,
                device_map=device_map,
            )
            
            self.is_loaded = True
            logger.info(f"Model loaded successfully. Device: {LLM_DEVICE}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    
    def format_prompt(
        self,
        messages: list,
        tools: list = None,
    ) -> str:
        """Format prompt using tokenizer.apply_chat_template."""
        if not self.is_loaded:
            self.load_model()
        
        try:
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                tools=tools if tools else [],
                add_generation_prompt=True
            )
            return prompt
        except Exception as e:
            logger.error(f"Error formatting prompt: {str(e)}")
            raise
    
    def generate_response(
        self,
        messages: list,
        tools: list = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response using the LLM with proper chat template formatting."""
        if not self.is_loaded:
            self.load_model()
        
        try:
            # Format prompt using apply_chat_template
            prompt = self.format_prompt(messages, tools)
            logger.debug(f"Formatted prompt:\n{prompt}")
            
            # Tokenize
            inputs = self.tokenizer(prompt, return_tensors="pt")
            
            model_device = next(self.model.parameters()).device
            inputs = {k: v.to(model_device) for k, v in inputs.items()}
            
            # Set pad token if not set
            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.config.pad_token_id = self.tokenizer.pad_token_id
            
            # Generate response
            with torch.inference_mode():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    pad_token_id=self.tokenizer.pad_token_id,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.9,
                )
            
            # Decode only the new tokens (skip input)
            input_length = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_length:]
            response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    async def generate_response_stream(
        self,
        messages: list,
        tools: list = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ):
        """Stream a response using the LLM.

        Yields text chunks as they are generated.
        Token limit is enforced via max_new_tokens=max_tokens.
        """
        if not self.is_loaded:
            self.load_model()

        prompt = self.format_prompt(messages, tools)
        inputs = self.tokenizer(prompt, return_tensors="pt")

        model_device = next(self.model.parameters()).device
        inputs = {k: v.to(model_device) for k, v in inputs.items()}

        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.config.pad_token_id = self.tokenizer.pad_token_id

        streamer = TextIteratorStreamer(self.tokenizer, skip_special_tokens=True)

        out_q: "queue.Queue[Optional[str]]" = queue.Queue()

        gen_kwargs = dict(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            pad_token_id=self.tokenizer.pad_token_id,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            streamer=streamer,
        )

        def _run_generate():
            try:
                with torch.inference_mode():
                    self.model.generate(**gen_kwargs)
            except Exception as e:
                logger.error(f"Error during streaming generation: {str(e)}")
                # TextIteratorStreamer does not have a great way to propagate
                # exceptions; the request will end when streamer is exhausted.

        def _drain_streamer():
            try:
                for piece in streamer:
                    out_q.put(piece)
            finally:
                out_q.put(None)

        gen_thread = threading.Thread(target=_run_generate, daemon=True)
        drain_thread = threading.Thread(target=_drain_streamer, daemon=True)
        gen_thread.start()
        drain_thread.start()

        while True:
            chunk = await asyncio.to_thread(out_q.get)
            if chunk is None:
                break
            yield chunk


# Global LLM manager
llm_manager = LLMManager()

# ============================================================================
# MCP Tools Wrapper
# ============================================================================

class ToolsWrapper:
    """Wrapper for accessing MCP tools."""
    
    TOOLS = {
        "get_vessel_locations": {
            "function": get_vessel_locations,
            "params": {"mmsi": int},
            "description": "Get all recorded positions for a vessel"
        },
        "get_vessel_current_position": {
            "function": get_vessel_current_position,
            "params": {"mmsi": int},
            "description": "Get the most recent position of a vessel"
        },
        "ship_following_analysis": {
            "function": ship_following_analysis,
            "params": {"mmsi1": int, "mmsi2": int},
            "description": "Determine if one vessel has been following another"
        },
        "get_location_context": {
            "function": get_location_context,
            "params": {"latitude": float, "longitude": float},
            "description": "Get geographic context for coordinates"
        },
        "get_distance_between": {
            "function": get_distance_between,
            "params": {"lat1": float, "lon1": float, "lat2": float, "lon2": float},
            "description": "Calculate distance between two points"
        },
        "identify_maritime_region": {
            "function": identify_maritime_region,
            "params": {"latitude": float, "longitude": float},
            "description": "Identify maritime region for coordinates"
        },
        "find_nearest_port": {
            "function": find_nearest_port,
            "params": {"latitude": float, "longitude": float},
            "description": "Find nearest major port"
        },
        "find_nearest_waterway": {
            "function": find_nearest_waterway,
            "params": {"latitude": float, "longitude": float},
            "description": "Find nearest strategic waterway"
        },
        "calculate_fleet_position": {
            "function": calculate_fleet_position,
            "params": {"fleet_name": str},
            "description": "Calculate average fleet position"
        },
        "is_ship_in_fleet": {
            "function": is_ship_in_fleet,
            "params": {"mmsi": int},
            "description": "Check if vessel is in fleet proximity"
        },
        "get_vessel_destination": {
            "function": get_vessel_destination,
            "params": {"mmsi": int, "number_detections": (int, 300)},
            "description": "Predict vessel heading"
        },
        "get_database_info": {
            "function": get_database_info,
            "params": {},
            "description": "Get basic SQLite database info (tables and columns)"
        },
        "query_database": {
            "function": query_database,
            "params": {"sql_query": str, "max_rows": (int, 200)},
            "description": "Execute a read-only SQL SELECT query against the AIS database and return results as JSON"
        },
    }
    
    async def is_reachable(self) -> bool:
        """Tools are always reachable since they're imported directly."""
        return True
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool directly."""
        if tool_name not in self.TOOLS:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        try:
            tool_info = self.TOOLS[tool_name]
            func = tool_info["function"]
            result = func(**arguments)
            
            # Parse JSON result
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return {"result": result}
            return {"result": result}
        except Exception as e:
            logger.error(f"Tool error: {str(e)}")
            raise
    
    def list_tools(self) -> list[dict]:
        """Get list of available tools."""
        tools_list = []
        for name, info in self.TOOLS.items():
            tools_list.append({
                "name": name,
                "description": info["description"]
            })
        return tools_list


# Global tools wrapper
tools_wrapper = ToolsWrapper()

# ============================================================================
# Query Handler
# ============================================================================

class QueryHandler:
    """Handles vessel queries by coordinating LLM and MCP tools."""

    def __init__(self, llm: LLMManager, tools: ToolsWrapper):
        self.llm = llm
        self.tools = tools

    def build_llm_tools_schema(self) -> list:
        """Build OpenAI-compatible tools schema for the LLM."""
        llm_tools: list[dict] = []
        for tool_name, tool_info in self.tools.TOOLS.items():
            properties: dict = {}
            required: list[str] = []
            for param_name, param_type in tool_info["params"].items():
                if isinstance(param_type, tuple):
                    param_type, default = param_type
                    properties[param_name] = {
                        "type": param_type.__name__,
                        "description": f"Parameter {param_name} (default: {default})",
                    }
                else:
                    properties[param_name] = {
                        "type": param_type.__name__,
                        "description": f"Parameter {param_name}",
                    }
                    required.append(param_name)

            llm_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_info["description"],
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )

        return llm_tools

    def _extract_tool_calls(self, llm_text: str) -> list[dict]:
        """Extract tool calls from LLM output."""
        tool_calls: list[dict] = []

        blocks = re.findall(r"<tool_call>(.*?)</tool_call>", llm_text or "", re.DOTALL)
        for block in blocks:
            func_match = re.search(r"<function=([^>]+)>", block)
            if not func_match:
                continue
            func_name = func_match.group(1).strip()

            params: dict = {}
            for p in re.finditer(r"<parameter=([^>]+)>(.*?)</parameter>", block, re.DOTALL):
                params[p.group(1).strip()] = p.group(2).strip()

            tool_calls.append({"name": func_name, "arguments": params})

        if tool_calls:
            return tool_calls

        stripped = (llm_text or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "name" in obj:
                    tool_calls.append(
                        {
                            "name": obj.get("name"),
                            "arguments": obj.get("arguments", {}) or {},
                        }
                    )
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _coerce_tool_arguments(self, tool_name: str, raw_args: dict) -> dict:
        """Coerce raw tool args (often strings) to declared Python types."""
        if tool_name not in self.tools.TOOLS:
            return raw_args

        spec = self.tools.TOOLS[tool_name]["params"]
        coerced: dict = {}

        for param_name, param_type in spec.items():
            default = None
            is_optional = False
            if isinstance(param_type, tuple):
                param_type, default = param_type
                is_optional = True

            if param_name not in raw_args:
                if is_optional:
                    coerced[param_name] = default
                continue

            value = raw_args[param_name]
            try:
                if param_type is int:
                    coerced[param_name] = int(value)
                elif param_type is float:
                    coerced[param_name] = float(value)
                elif param_type is str:
                    coerced[param_name] = str(value)
                else:
                    coerced[param_name] = value
            except Exception:
                coerced[param_name] = value

        for k, v in (raw_args or {}).items():
            if k not in coerced:
                coerced[k] = v

        return coerced

    def _strip_tool_blocks(self, text: str) -> str:
        """Remove tool call markup from a final answer."""
        return re.sub(r"<tool_call>.*?</tool_call>", "", text or "", flags=re.DOTALL).strip()

    async def handle_query(
        self,
        question: str,
        max_tokens: int = 100000,
        temperature: float = 0.7,
    ) -> QueryResponse:
        """Handle a vessel query."""
        import time

        start_time = time.time()
        tools_used: list[str] = []

        llm_tools = self.build_llm_tools_schema()
        system_prompt = (
            "You are a maritime intelligence assistant specialized in AIS (Automatic Identification System) vessel data. "
            "Use tools when needed to answer accurately."
        )
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        logger.info(f"Query: {question}")

        max_tool_iterations = int(os.getenv("LLM_MAX_TOOL_ITERATIONS", "5"))
        answer = ""

        for _ in range(max_tool_iterations):
            llm_text = self.llm.generate_response(
                messages,
                tools=llm_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            messages.append({"role": "assistant", "content": llm_text})

            tool_calls = self._extract_tool_calls(llm_text)
            if not tool_calls:
                answer = self._strip_tool_blocks(llm_text)
                break

            for call in tool_calls:
                tool_name = call.get("name")
                raw_args = call.get("arguments", {}) or {}
                if not tool_name:
                    continue

                coerced_args = self._coerce_tool_arguments(tool_name, raw_args)
                tools_used.append(tool_name)

                try:
                    tool_result = await self.tools.call_tool(tool_name, coerced_args)
                    tool_content = json.dumps(tool_result, ensure_ascii=False)
                except Exception as e:
                    tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)

                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": tool_content,
                })

        if not answer:
            last_assistant = ""
            for m in reversed(messages):
                if m.get("role") == "assistant":
                    last_assistant = m.get("content", "")
                    break
            answer = self._strip_tool_blocks(last_assistant)

        execution_time = time.time() - start_time
        return QueryResponse(
            question=question,
            answer=answer,
            tools_used=tools_used,
            execution_time_seconds=execution_time,
            timestamp=datetime.utcnow().isoformat(),
        )

    async def stream_debug_query(
        self,
        question: str,
        max_tokens: int = 100000,
        temperature: float = 0.7,
    ):
        """Stream a full tool-using conversation for debugging."""
        import time

        start_time = time.time()
        tools_used: list[str] = []

        llm_tools = self.build_llm_tools_schema()
        system_prompt = (
            "You are a maritime intelligence assistant specialized in AIS (Automatic Identification System) vessel data. "
            "Use tools when needed to answer accurately."
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        remaining_new_tokens = max(0, int(max_tokens))
        max_tool_iterations = int(os.getenv("LLM_MAX_TOOL_ITERATIONS", "5"))
        answer = ""

        for iteration in range(max_tool_iterations):
            if remaining_new_tokens <= 0:
                break

            yield f"data: {json.dumps({'type': 'iteration_start', 'iteration': iteration})}\\n\\n"

            assistant_parts: list[str] = []
            async for chunk in self.llm.generate_response_stream(
                messages,
                tools=llm_tools,
                max_tokens=remaining_new_tokens,
                temperature=temperature,
            ):
                assistant_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'assistant_delta', 'iteration': iteration, 'content': chunk}, ensure_ascii=False)}\\n\\n"

            assistant_text = "".join(assistant_parts).strip()
            messages.append({"role": "assistant", "content": assistant_text})
            yield f"data: {json.dumps({'type': 'assistant_end', 'iteration': iteration})}\\n\\n"

            try:
                produced = len(self.llm.tokenizer(assistant_text, add_special_tokens=False).input_ids)
            except Exception:
                produced = 0
            remaining_new_tokens = max(0, remaining_new_tokens - produced)
            yield f"data: {json.dumps({'type': 'budget', 'remaining_new_tokens': remaining_new_tokens})}\\n\\n"

            tool_calls = self._extract_tool_calls(assistant_text)
            if not tool_calls:
                answer = self._strip_tool_blocks(assistant_text)
                break

            for call in tool_calls:
                tool_name = call.get("name")
                raw_args = call.get("arguments", {}) or {}
                if not tool_name:
                    continue

                coerced_args = self._coerce_tool_arguments(tool_name, raw_args)
                tools_used.append(tool_name)
                yield f"data: {json.dumps({'type': 'tool_call', 'iteration': iteration, 'name': tool_name, 'arguments': coerced_args}, ensure_ascii=False)}\\n\\n"

                try:
                    tool_result = await self.tools.call_tool(tool_name, coerced_args)
                    tool_result_obj = tool_result
                except Exception as e:
                    tool_result_obj = {"error": str(e)}

                yield f"data: {json.dumps({'type': 'tool_result', 'iteration': iteration, 'name': tool_name, 'result': tool_result_obj}, ensure_ascii=False)}\\n\\n"
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(tool_result_obj, ensure_ascii=False),
                })

        if not answer:
            last_assistant = ""
            for m in reversed(messages):
                if m.get("role") == "assistant":
                    last_assistant = m.get("content", "")
                    break
            answer = self._strip_tool_blocks(last_assistant)

        elapsed = time.time() - start_time
        yield f"data: {json.dumps({'type': 'final', 'answer': answer, 'tools_used': tools_used, 'execution_time_seconds': elapsed}, ensure_ascii=False)}\\n\\n"


# Global query handler
query_handler = QueryHandler(llm_manager, tools_wrapper)

# ============================================================================
# FastAPI Routes
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health."""
    tools_reachable = await tools_wrapper.is_reachable()
    
    return HealthResponse(
        status="healthy" if tools_reachable else "degraded",
        llm_loaded=llm_manager.is_loaded,
        mcp_reachable=tools_reachable,
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/query", response_model=QueryResponse)
async def query_vessels(request: QueryRequest) -> QueryResponse:
    """
    Query vessel data using natural language.
    
    Args:
        request: QueryRequest containing the question and parameters
    
    Returns:
        QueryResponse with the answer and metadata
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        # Tools are always available since they're imported directly
        
        # Load LLM if needed
        if not llm_manager.is_loaded:
            llm_manager.load_model()
        
        # Handle query
        response = await query_handler.handle_query(
            question=request.question,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Query processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query_stream")
async def query_vessels_stream(request: QueryRequest):
    """Query vessel data and stream the LLM response as it is generated.

    This endpoint returns Server-Sent Events (SSE). Each event is a JSON object:
    - {"type": "assistant_delta", "content": "...", "iteration": 0}
    - {"type": "tool_call", "name": "...", "arguments": {...}, "iteration": 0}
    - {"type": "tool_result", "name": "...", "result": {...}, "iteration": 0}
    - {"type": "final", "answer": "...", "tools_used": [...], "execution_time_seconds": ...}
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not llm_manager.is_loaded:
        llm_manager.load_model()

    async def event_generator():
        async for event in query_handler.stream_debug_query(
            question=request.question,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/tools")
async def list_available_tools():
    """List available MCP tools."""
    try:
        tools = tools_wrapper.list_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Failed to list tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tools")


@app.post("/tools/{tool_name}")
async def call_mcp_tool(tool_name: str, arguments: dict):
    """
    Call a specific MCP tool.
    
    Args:
        tool_name: Name of the tool to call
        arguments: Arguments for the tool
    
    Returns:
        Tool result
    """
    try:
        result = await tools_wrapper.call_tool(tool_name, arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool call failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """On server startup."""
    # check if SQLite database exists, if not create it
    if not os.path.exists(SQLITE_PATH):
        logger.info("SQLite database not found, creating from JSON...")
        main()
    else:
        logger.info("SQLite database found, skipping creation.")

    logger.info("AIS Vessel Intelligence LLM Server starting...")
    logger.info(f"LLM Model: {LLM_MODEL}")
    logger.info("MCP tools available (direct import)")
    
    # Check tool availability
    tools_available = await tools_wrapper.is_reachable()
    if tools_available:
        logger.info(f"Available tools: {len(tools_wrapper.list_tools())}")
    else:
        logger.warning("Tools not available")


@app.on_event("shutdown")
async def shutdown_event():
    """On server shutdown."""
    logger.info("AIS Vessel Intelligence LLM Server shutting down...")


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("LLM_SERVER_PORT", 8000))
    host = os.getenv("LLM_SERVER_HOST", "0.0.0.0")
    
    uvicorn.run(
        "llm_server:app",
        host=host,
        port=port,
        reload=False
    )
