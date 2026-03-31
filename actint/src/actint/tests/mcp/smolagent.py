from smolagents import ToolCallingAgent, WebSearchTool

agent = ToolCallingAgent(tools=[WebSearchTool()], model=model)