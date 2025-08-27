from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gaming-trends-server")

@mcp.tool(name="get-gaming-trends")
async def example_tool(param: str) -> str:
    """Fetch trending gaming topics.

    Args:
        param: Example parameter, can be anything.

    Returns:
        Example result.
    """
    return "example result"

if __name__ == "__main__":
    mcp.run(transport="stdio")
