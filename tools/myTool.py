import sys, json
from mcp.server.fastmcp import FastMCP
from typing import Any

DEFAULT_CONFIG = {
    "name": "get-gaming-trends",
    "description": "Fetch trending gaming topics",
    "return_value": "Example result"
}

tool_config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
mcp = FastMCP(tool_config.get("name", "dynamic-tool-server"))

@mcp.tool(name=tool_config["name"], description=tool_config["description"])
async def dynamic_tool(param: str = "") -> Any:
    """Dynamic tool.

    Args:
        param: Arbitrary input.
    """
    return tool_config.get("return_value", "default result")

if __name__ == "__main__":
    mcp.run(transport="stdio")