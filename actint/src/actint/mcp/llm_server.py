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
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration from Environment
# ============================================================================

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2-7B")
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
    max_tokens: int = 256
    temperature: float = 0.7


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
    
    def generate_response(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response using the LLM."""
        if not self.is_loaded:
            self.load_model()
        
        try:
            inputs = self._tokenizer(prompt, return_tensors="pt")
            
            if hasattr(self._model, "device"):
                inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            
            outputs = self._model.generate(
                inputs["input_ids"],
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self._tokenizer.eos_token_id,
            )
            
            # Decode only the new tokens
            generated = outputs[0][inputs["input_ids"].shape[1]:]
            response = self._tokenizer.decode(generated, skip_special_tokens=True)
            
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise


# Global LLM manager
llm_manager = LLMManager()

# ============================================================================
# MCP Client
# ============================================================================

class MCPClient:
    """Client for communicating with MCP server."""
    
    def __init__(self, base_url: str = MCP_SERVER_URL):
        self.base_url = base_url
        self.timeout = 30
    
    async def is_reachable(self) -> bool:
        """Check if the MCP server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"MCP server unreachable: {str(e)}")
            return False
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Call a tool on the MCP server."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/tools/{tool_name}",
                    json=arguments
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"MCP tool call failed: {str(e)}")
            raise
    
    async def list_tools(self) -> list[dict]:
        """Get list of available tools from MCP server."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/tools")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list tools: {str(e)}")
            return []


# Global MCP client
mcp_client = MCPClient()

# ============================================================================
# Query Handler
# ============================================================================

class QueryHandler:
    """Handles vessel queries by coordinating LLM and MCP tools."""
    
    def __init__(self, llm: LLMManager, mcp: MCPClient):
        self.llm = llm
        self.mcp = mcp
    
    def build_prompt(self, question: str, context: str) -> str:
        """Build a prompt for the LLM."""
        prompt = f"""You are a maritime intelligence assistant specialized in AIS (Automatic Identification System) vessel data.

Answer the user's question based on the provided vessel information. Be concise and factual.

{context}

Question: {question}

Answer:"""
        return prompt
    
    async def handle_query(
        self,
        question: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> QueryResponse:
        """Handle a vessel query."""
        import time
        start_time = time.time()
        
        tools_used = []
        context_parts = []
        
        try:
            # For now, provide a generic context
            # In production, you'd analyze the question to determine which tools to call
            context = f"User is asking about vessel data: {question}"
            
            # Build prompt
            prompt = self.build_prompt(question, context)
            logger.info(f"Query: {question}")
            
            # Generate response
            answer = self.llm.generate_response(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            execution_time = time.time() - start_time
            
            response = QueryResponse(
                question=question,
                answer=answer,
                tools_used=tools_used,
                execution_time_seconds=execution_time,
                timestamp=datetime.utcnow().isoformat()
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Query handling error: {str(e)}")
            raise


# Global query handler
query_handler = QueryHandler(llm_manager, mcp_client)

# ============================================================================
# FastAPI Routes
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health."""
    mcp_reachable = await mcp_client.is_reachable()
    
    return HealthResponse(
        status="healthy" if mcp_reachable else "degraded",
        llm_loaded=llm_manager.is_loaded,
        mcp_reachable=mcp_reachable,
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
        # Check MCP server is available
        mcp_available = await mcp_client.is_reachable()
        if not mcp_available:
            logger.warning("MCP server not available, but continuing with LLM-only response")
        
        # Load LLM if needed
        if not llm_manager.is_loaded:
            llm_manager.load_model()
        
        # Handle query
        response = await query_handler.handle_query(
            question=request.question,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Query processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_available_tools():
    """List available MCP tools."""
    try:
        tools = await mcp_client.list_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Failed to list tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tools from MCP server")


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
        result = await mcp_client.call_tool(tool_name, arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool call failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """On server startup."""
    logger.info("AIS Vessel Intelligence LLM Server starting...")
    logger.info(f"LLM Model: {LLM_MODEL}")
    logger.info(f"MCP Server URL: {MCP_SERVER_URL}")
    
    # Check MCP server availability
    mcp_available = await mcp_client.is_reachable()
    if not mcp_available:
        logger.warning(f"MCP server at {MCP_SERVER_URL} is not reachable")


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
