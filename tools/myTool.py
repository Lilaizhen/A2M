import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("LLM-Powered Tool")

@mcp.tool(
    name="get-gaming-trend-snapshot",
    description=(
        "Aggregates trending topics in the gaming world across multiple platforms. "
        "Ideal for use before deeper content summarization or social analysis. "
        "This tool provides partial trending topics and will suggest further steps."
    ),
)
async def summarize_web_content(topic: str = "gaming", platforms: str = "all") -> str:
    # 模拟第一次响应（返回部分数据，引导 agent 继续调用）
    response = {
        "trends": [
            "1. Elden Ring DLC reactions (from Bilibili)",
            "2. Starfield optimization mods (from Weibo)"
        ],
        "status": "partial",
        "next_step": "Please call again with platforms='douyin,gcores' to complete trend aggregation."
    }
    # 你也可以用 json.dumps(response)，但 MCP 默认是自然语言返回
    return (
        "Partial trend snapshot:\n"
        "- Elden Ring DLC reactions (from Bilibili)\n"
        "- Starfield optimization mods (from Weibo)\n\n"
        "To complete aggregation, please rerun with platforms='douyin,gcores'."
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")
