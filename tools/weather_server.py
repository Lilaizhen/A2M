from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")

@mcp.tool()
async def get_temperature(location: str) -> str:
    """根据地址返回当前温度"""
    fake_data = {
        "Beijing": "28°C",
        "Shanghai": "30°C",
        "New York": "25°C",
    }
    return f"The temperature in {location} is {fake_data.get(location, 'unknown')}"

if __name__ == "__main__":
    mcp.run(transport="stdio")  # ✅ 改为8001，避免冲突