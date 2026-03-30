"""
AIS Vessel Intelligence MCP System.

A Model Context Protocol (MCP) implementation for querying and analyzing
AIS vessel data through natural language interfaces.

Components:
- mcp_server: Standalone MCP server exposing vessel intelligence tools
- llm_server: FastAPI server hosting Qwen LLM with MCP integration
"""

from .mcp_server import server
from .llm_server import app

__all__ = ["server", "app"]
__version__ = "1.0.0"
