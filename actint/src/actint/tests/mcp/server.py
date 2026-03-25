from fastmcp import FastMCP

mcp = FastMCP("LocalServer")

@mcp.tool()
def get_weather(location: str) -> str:
    """Get the current weather for a specific location.
    
    Args:
        location: The location to get the current weather for, in the format "City, State, Country".

    Returns:
        A sentence describing the weather, including temperature and conditions.
    """
    return f"The weather in {location} is currently 72°F and sunny."

if __name__ == "__main__":
    mcp.run()