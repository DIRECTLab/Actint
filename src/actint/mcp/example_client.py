#!/usr/bin/env python3
"""
Example client for AIS Vessel Intelligence MCP System.

Demonstrates how to query the LLM server for vessel information.
"""

import os
import json
import httpx
from typing import Optional


class AISSysClient:
    """Client for AIS Vessel Intelligence System."""
    
    def __init__(
        self,
        llm_server_url: str = "http://localhost:8000",
        mcp_server_url: str = "http://localhost:8001",
        timeout: int = 30
    ):
        self.llm_base_url = llm_server_url
        self.mcp_base_url = mcp_server_url
        self.timeout = timeout
    
    def query(
        self,
        question: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> dict:
        """Query the vessel intelligence system."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.llm_base_url}/query",
                json={
                    "question": question,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
            response.raise_for_status()
            return response.json()
    
    def health(self) -> dict:
        """Check system health."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.llm_base_url}/health")
            response.raise_for_status()
            return response.json()
    
    def list_tools(self) -> list:
        """List available MCP tools."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.llm_base_url}/tools")
            response.raise_for_status()
            return response.json().get("tools", [])
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a specific tool directly."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.llm_base_url}/tools/{tool_name}",
                json=arguments
            )
            response.raise_for_status()
            return response.json()


def main():
    """Run example queries."""
    client = AISSysClient()
    
    # Check health
    print("=" * 60)
    print("System Health Check")
    print("=" * 60)
    try:
        health = client.health()
        print(json.dumps(health, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure both MCP and LLM servers are running!")
        return
    
    print("\n")
    
    # Example queries
    example_queries = [
        "Where is USS KIDD right now?",
        "What maritime region is the vessel at coordinates 35.2, 139.66 in?",
        "How far is the closest port from coordinates 32.71, -117.16?",
        "What is the current position of the vessel with MMSI 368011000?",
    ]
    
    print("=" * 60)
    print("Example Queries")
    print("=" * 60)
    
    for question in example_queries:
        print(f"\nQuestion: {question}")
        print("-" * 60)
        
        try:
            result = client.query(question)
            
            print(f"Answer: {result['answer']}")
            print(f"Execution Time: {result['execution_time_seconds']:.3f}s")
            if result['tools_used']:
                print(f"Tools Used: {', '.join(result['tools_used'])}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n")
    
    # Direct tool call example
    print("=" * 60)
    print("Direct Tool Call Example")
    print("=" * 60)
    
    print("\nCalling: find_nearest_port")
    print("Arguments: latitude=32.7157, longitude=-117.1611")
    print("-" * 60)
    
    try:
        result = client.call_tool(
            "find_nearest_port",
            {"latitude": 32.7157, "longitude": -117.1611}
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
