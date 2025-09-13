import asyncio
import json
import os
import time
import re
from datetime import datetime
import argparse
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback

# 加载自定义模块
from src.utils.logging_config import setup_run_logger, log_and_echo
from src.utils.tool_functions import truncate_tool_outputs, _now, _as_text, render_behavior_from_trace, _convert_relative_paths_in_text
from src.mcp_client.client import LimitedMCPClient
from src.agents.agent_utils import format_agent_step
from src.evaluators.task_evaluator import judge_task_completion
from src.data_loaders.data_loader import load_mcp_configs_from_live_config, load_tool_to_mcp_mapping, fetch_server_tool_names, load_dataset
from src.core.executor import TaskExecutor
from src.core.agent_runner import run_agent_with_streaming
import shutil

load_dotenv()  # 加载 .env 文件中的环境变量


def _reset_annotated_data():
    """
    重置annotated_data文件夹到备份状态
    """
    from src.core.agent_executor import reset_annotated_data
    reset_annotated_data("./annotated_data", "./annotated_data_backup")


# --- 全局配置 ---
RESULTS_DIR = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
os.makedirs(RESULTS_DIR, exist_ok=True)

RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")

# 可选：限制单条工具输出写入轨迹的最大字符数，避免结果过大
MAX_TOOL_OUTPUT_CHARS = 8000


async def main(dataset, attack: bool = True, attack_dataset_path: str = None, model_name: str = "glm-4.5", dataset_type: str = "all"):
    # --- 全局配置 ---
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    RESULTS_DIR = f"results/{timestamp}_{model_name}_{dataset_type}"
    os.makedirs(RESULTS_DIR, exist_ok=True)

    RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
    RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")
    
    setup_run_logger(RUN_LOG_FILE)

    all_mcp_config = load_mcp_configs_from_live_config("./configs/live_mcp.json")
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping("./configs/tool2mcp.json")
    
    # 加载attack数据集（如果提供）
    attack_tool_mapping = {}
    if attack_dataset_path:
        try:
            with open(attack_dataset_path, "r", encoding="utf-8") as f:
                attack_data = json.load(f)
                attack_tool_mapping = {item["task_id"]: item["attack_tools"] for item in attack_data}
        except Exception as e:
            log_and_echo(f"⚠️ 加载attack数据集失败: {e}")

    # 从配置文件加载代理设置
    proxy_config_path = "./configs/proxy_config.json"
    proxy_settings = {}
    if os.path.exists(proxy_config_path):
        try:
            with open(proxy_config_path, "r", encoding="utf-8") as f:
                proxy_settings = json.load(f)
        except Exception as e:
            log_and_echo(f"⚠️ 加载代理配置文件失败: {e}")
    else:
        log_and_echo("ℹ️ 代理配置文件不存在，不添加代理设置")
    
    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(".py"):
            tool["args"][0] = os.path.abspath(tool["args"][0])
        
        # 如果配置文件中有代理设置，则添加到环境变量中（不覆盖已有的环境变量）
        if proxy_settings:
            if "env" not in tool:
                tool["env"] = {}
            for key, value in proxy_settings.items():
                if key not in tool["env"]:
                    tool["env"][key] = value

    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://apis.iflow.cn/v1")  # 默认值保持不变
    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=model_name,
        streaming=True,
        temperature=0.0,
        timeout=100,   # 业务 LLM 100s
        max_retries=1
    )

    results_summary = []

    for task in dataset:
        task_id = task["id"]
        task_desc = task["description"]
        user_prompt = task["input"]
        expected_tools = task["expected_tools"]

        task_start_time = time.time()
        log_and_echo(f"=============== 运行任务 {task_id}（{task_desc}） ===============")

        # === 使用annotated_data目录 ===
        temp_dir = "./annotated_data"
        log_and_echo(f"🔧 使用annotated_data目录: {temp_dir}")
        
        # 重置annotated_data文件夹到备份状态
        _reset_annotated_data()
        log_and_echo("🔄 重置annotated_data目录到备份状态")

        try:
            # 保持任务描述和输入不变
            original_task_desc = task_desc
            original_user_prompt = user_prompt

            # === 构造 filtered_config（包含 expected 工具 + 可选 mytool）===
            filtered_config = {}
            required_mcp_servers = set()

            if expected_tools:
                for tool_name in expected_tools:
                    if tool_name in tool_to_mcp:
                        mcp_server_names = tool_to_mcp[tool_name]
                        if isinstance(mcp_server_names, list):
                            required_mcp_servers.update(mcp_server_names)
                        else:
                            required_mcp_servers.add(mcp_server_names)

            mytool_server_key = "mytool"
            mytool_server_path = "./tools/myTool.py"
            if attack:
                mytool_config = {
                    "command": "python",
                    "args": [os.path.abspath(mytool_server_path)],
                    "transport": "stdio"
                }
                if attack_dataset_path and task_id in attack_tool_mapping and attack_tool_mapping[task_id]:
                    attack_tool = attack_tool_mapping[task_id][0]
                    config_json = json.dumps(attack_tool, ensure_ascii=False)
                    mytool_config["args"].extend([config_json])
                filtered_config[mytool_server_key] = mytool_config

            for server_name in required_mcp_servers:
                if server_name in mcp_configs:
                    filtered_config[server_name] = mcp_configs[server_name].copy()
                    filtered_config[server_name].setdefault("transport", "stdio")
                    if (filtered_config[server_name]["command"] == "python" and
                        filtered_config[server_name].get("args") and
                        filtered_config[server_name]["args"][0].endswith(".py")):
                        filtered_config[server_name]["args"][0] = os.path.abspath(filtered_config[server_name]["args"][0])
                    
                    # 如果配置文件中有代理设置，则添加到环境变量中（不覆盖已有的环境变量）
                    if proxy_settings:
                        if "env" not in filtered_config[server_name]:
                            filtered_config[server_name]["env"] = {}
                        for key, value in proxy_settings.items():
                            if key not in filtered_config[server_name]["env"]:
                                filtered_config[server_name]["env"][key] = value

            log_and_echo("🧪 工具加载: " + str(list(filtered_config.keys())))

            # === 动态获取 mytool 的工具名集合 ===
            mytool_tool_names: set[str] = set()
            if attack and mytool_server_key in filtered_config:
                try:
                    mytool_tool_names = await fetch_server_tool_names(mytool_server_key, filtered_config[mytool_server_key], MultiServerMCPClient)
                    log_and_echo(f"mytool 工具清单: {sorted(mytool_tool_names)}")
                except Exception as e:
                    log_and_echo(f"⚠️ 获取 mytool 工具名失败，将无法区分其调用：{e}")
                    mytool_tool_names = set()

            # --- 加载 MCP 工具（使用 LimitedMCPClient，带超时与返回截断）---
            try:
                limited = LimitedMCPClient(
                    filtered_config,
                    max_response_length=5000,
                    max_list_length=100,
                    max_category_items=20,
                    timeout=30
                )
                tools = await limited.get_tools()
            except Exception as e:
                log_and_echo(f"❌ 加载 MCP 工具失败: {e}")
                task_end_time = time.time()
                task_execution_time = task_end_time - task_start_time

                results_summary.append({
                    "task_id": task_id,
                    "input": user_prompt,
                    "expected_tools": expected_tools,
                    "agent_final_response": "MCP 工具加载失败",
                    "task_completed": False,
                    "completion_reason": {
                        "result": "未完成",
                        "reason": f"MCP 工具加载失败: {e.__class__.__name__}",
                        "failure_type": "mcp_error"
                    },
                    "execution_time_seconds": task_execution_time,
                    "total_tool_calls": 0,
                    "mytool_calls": 0,
                    "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
                    "action_trace": [
                        {"ts": _now(), "type": "user_input", "content": user_prompt}
                    ]
                })
                continue

            # --- 创建 Agent 并行（容错） ---
            final_response = ""
            action_trace = []  # 行动轨迹
            token_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

            # 任务开始即记录用户输入
            action_trace.append({
                "ts": _now(),
                "type": "user_input",
                "content": user_prompt
            })

            try:
                # 使用统一的agent执行模块
                agent_result = await run_agent_with_streaming(
                    llm=llm,
                    tools=tools,
                    task_id=f"test-{task_id}",
                    user_prompt=user_prompt,
                    use_tool_lock=True
                )

                final_response = agent_result["final_response"]
                action_trace = agent_result["action_trace"]
                token_usage = agent_result["token_usage"]

            except Exception as e:
                log_and_echo(f"❌ 运行代理失败: {e}")
                task_end_time = time.time()
                task_execution_time = task_end_time - task_start_time
                results_summary.append({
                    "task_id": task_id,
                    "input": user_prompt,
                    "expected_tools": expected_tools,
                    "agent_final_response": f"Agent 运行失败: {e}",
                    "task_completed": False,
                    "completion_reason": {
                        "result": "未完成",
                        "reason": f"Agent 运行失败: {e.__class__.__name__}",
                        "failure_type": "agent_error"
                    },
                    "execution_time_seconds": task_execution_time,
                    "total_tool_calls": sum(1 for x in action_trace if x.get("type") == "tool_call"),
                    "mytool_calls": sum(1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in mytool_tool_names),
                    "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
                    "action_trace": action_trace
                })
                continue

            # === 任务完成度判断（改为基于轨迹）===
            is_task_completed = False
            completion_json = {"result": "未知", "reason": "缺少必要信息", "failure_type": "unknown"}
            if action_trace and task_desc:
                behavior_text = render_behavior_from_trace(action_trace, max_tool_out_chars=2000)
                is_task_completed, _, completion_json = await judge_task_completion(
                    agent_behavior=behavior_text,
                    task_description=task_desc,
                    expected_tools=expected_tools
                )
            else:
                log_and_echo("⚠️  跳过任务完成度判断（缺少必要信息）")

            # 统计
            total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
            mytool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in mytool_tool_names)

            # 执行时间
            task_end_time = time.time()
            task_execution_time = task_end_time - task_start_time

            results_summary.append({
                "task_id": task_id,
                "input": user_prompt,
                "expected_tools": expected_tools,
                "agent_final_response": final_response,
                "task_completed": is_task_completed,
                "completion_reason": completion_json,
                "execution_time_seconds": task_execution_time,
                "total_tool_calls": total_tool_calls,
                "mytool_calls": mytool_calls,
                "token_usage": token_usage,
                "action_trace": action_trace
            })

        finally:
            # 不需要清理临时目录
            log_and_echo(f"ℹ️  使用annotated_data目录，无需清理")

    # === 汇总结果 ===
    total_tasks = len(results_summary)
    completed_tasks = sum(1 for r in results_summary if r["task_completed"])
    completion_rate = (0 if total_tasks == 0 else completed_tasks / total_tasks * 100)
    overall_total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results_summary)
    overall_mytool_calls = sum(r.get("mytool_calls", 0) for r in results_summary)
    
    overall_token_usage = {
        "total_tokens": sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results_summary),
        "prompt_tokens": sum(r.get("token_usage", {}).get("prompt_tokens", 0) for r in results_summary),
        "completion_tokens": sum(r.get("token_usage", {}).get("completion_tokens", 0) for r in results_summary)
    }

    final_report = {
        "run_timestamp": datetime.now().isoformat(),
        "overall_statistics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": f"{completion_rate:.2f}%",
            "total_tool_calls": overall_total_tool_calls,
            "mytool_calls": overall_mytool_calls,
            "token_usage": overall_token_usage
        },
        "task_details": results_summary
    }

    with open(RESULT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print("\n================= 所有任务运行完毕 =================\n")
    print(f"📊 任务完成率: {completion_rate:.2f}% ({completed_tasks}/{total_tasks})")
    print(f"📊 总工具调用次数: {overall_total_tool_calls}，其中 mytool: {overall_mytool_calls}")
    print(f"📊 总token使用量: {overall_token_usage['total_tokens']} (提示: {overall_token_usage['prompt_tokens']}, 完成: {overall_token_usage['completion_tokens']})")
    print(f"📄 结果 JSON 路径: {RESULT_JSON_FILE}")
    print(f"📝 运行日志路径: {RUN_LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # 选择数据集：all、test、filter
    parser.add_argument(
        "--dataset",
        choices=["all", "test", "filter"],
        default="all",
        help=(
            "选择数据集：\n"
            "all=./datasets/all_annotations.json（默认）\n"
            "test=./datasets/test_prompts.json\n"
            "filter=./datasets/all_annotations_filter.json"
        )
    )
    parser.add_argument("--use-mytool", action="store_true", help="启用 mytool MCP server")
    parser.add_argument("--attack-dataset", type=str, help="attack数据集路径")
    args = parser.parse_args()

    # 路径映射
    if args.dataset == "test":
        data_path = "./datasets/test_prompts.json"
    elif args.dataset == "filter":
        data_path = "./datasets/all_annotations_filter.json"
    else:  # 默认 all
        data_path = "./datasets/all_annotations.json"

    dataset = load_dataset(data_path)
    
    # 再次确保所有任务中的相对路径都被转换为绝对路径
    if dataset:
        for task in dataset:
            if "description" in task:
                task["description"] = _convert_relative_paths_in_text(task["description"])
            if "input" in task:
                task["input"] = _convert_relative_paths_in_text(task["input"])
        
        asyncio.run(main(dataset, attack=args.use_mytool, attack_dataset_path=args.attack_dataset))
    else:
        print("错误: 没有找到任何有效的数据集文件")