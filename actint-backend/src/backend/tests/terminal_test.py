# In terminal_test.py
import asyncio
from backend.agent.agent import query_agent

async def main():
    print("Agent Terminal Interface Initialized. Type 'exit' to quit.")
    session_id = "local_terminal_1"
    
    while True:
        query = input("\nYou: ")
        if query.lower() in ['exit', 'quit']:
            break
            
        # Call query agent with NO additional UI tools
        # The agent will only have access to the base `ais_mcp_tools`
        response = await query_agent(query, session_id=session_id, additional_tools=[])
        print(f"\nAgent: {response}")

if __name__ == "__main__":
    asyncio.run(main())