import asyncio
import json
import os
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

def load_and_merge_mcp_configs(config_paths):
    merged_config = {}
    for path in config_paths:
        with open(path, "r", encoding="utf-8") as f:
            raw_config = json.load(f)
            cfg = raw_config.get("mcpServers", raw_config)
            merged_config.update(cfg)
    return merged_config

async def main():
    # === 1. 加载并合并多个 MCP 配置文件 ===
    config_files = [
        "./configs/mcp_config.json",
        "./configs/attack_mcp_config.json"
    ]
    all_mcp_config = load_and_merge_mcp_configs(config_files)

    # 补全本地路径并设置默认 transport
    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args"):
            tool["args"][0] = os.path.abspath(tool["args"][0])

    # === 2. 加载测试数据集 ===
    with open("./datasets/test_prompts.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # === 3. 初始化 LLM 模型 ===
    llm = ChatOpenAI(
        openai_api_key="sk-ulrlrftgwvyklbxqdvxgfkezoirtmiuegblozcsplognafaa",
        openai_api_base="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen3-32B",
        streaming=True,
        temperature=0.7
    )

    # === 4. 执行每一条任务 ===
    for task in dataset:
        task_id = task["id"]
        task_desc = task["description"]
        user_prompt = task["input"]
        expected_tools = task["expected_tools"]

        # 过滤出当前任务所需的工具配置
        # 当 expected_tools 为空时不过滤，使用所有工具
        if expected_tools:
            filtered_config = {
                alias: cfg for alias, cfg in all_mcp_config.items()
                if alias in expected_tools
            }
        else:
            filtered_config = all_mcp_config

        print(f"\n================= 运行任务 {task_id}（{task_desc}）=================\n")
        print(f"🧪 工具加载: {list(filtered_config.keys())}")

        # 构建 Agent 并执行对话
        client = MultiServerMCPClient(filtered_config)
        tools = await client.get_tools()
        agent = create_react_agent(llm, tools, checkpointer=MemorySaver())

        config = {"configurable": {"thread_id": f"test-{task_id}"}}
        user_input = {"role": "user", "content": user_prompt}

        async for step in agent.astream({"messages": [user_input]}, config, stream_mode="values"):
            step["messages"][-1].pretty_print()

if __name__ == "__main__":
    asyncio.run(main())
