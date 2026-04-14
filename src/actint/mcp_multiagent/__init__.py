"""
AIS Vessel Intelligence MCP Multi-Agent System.

A Model Context Protocol (MCP) implementation for querying and analyzing
AIS vessel data through natural language interfaces.

Components:
- mcp_server_reasoning: Coordinator server exposing delegation tools
- mcp_server_sql: SQL specialist server with read-only database tools
- mcp_server_map: Map specialist server with maritime geospatial tools
- mcp_server_math: Math specialist server with quantitative tools
- smolagent: Four-agent runtime (reasoning manager + SQL + map + math specialists)
"""
