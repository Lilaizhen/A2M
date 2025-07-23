from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Location")

@mcp.tool()
async def get_location() -> str:
    """Return current location"""
    return "Beijing"

if __name__ == "__main__":
    mcp.run(transport="stdio")
