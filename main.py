import asyncio
import json
import os
import logging
import time
from logging import StreamHandler, FileHandler
from datetime import datetime
import re
import argparse
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

load_dotenv()  # 加载 .env 文件中的环境变量

# --- 全局配置 ---
RESULTS_DIR = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
os.makedirs(RESULTS_DIR, exist_ok=True)

RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")


def setup_run_logger():
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = FileHandler(RUN_LOG_FILE, mode="w", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    logging.info("==== New run started. Logs will be written to %s ====", RUN_LOG_FILE)


def log_and_echo(text: str, level: int = logging.INFO):
    logging.log(level, "%s", text.rstrip("\n"))


def _pretty_json(x):
    if isinstance(x, str):
        try:
            return json.dumps(json.loads(x), ensure_ascii=False, indent=2)
        except Exception:
            return x
    return json.dumps(x, ensure_ascii=False, indent=2)


def truncate_tool_outputs(response_text: str, max_lines_per_tool: int = 10) -> str:
    """
    截断工具输出内容，只保留前几行，避免撑爆上下文
    """
    if not response_text:
        return response_text
    
    lines = response_text.split('\n')
    truncated_lines = []
    in_tool_output = False
    tool_line_count = 0
    
    for line in lines:
        if "================================== Tool Output" in line:
            in_tool_output = True
            tool_line_count = 0
            truncated_lines.append(line)
        elif in_tool_output and "==================================" in line and "Tool Output" not in line:
            in_tool_output = False
            truncated_lines.append(line)
        elif in_tool_output:
            if tool_line_count < max_lines_per_tool:
                truncated_lines.append(line)
                tool_line_count += 1
            elif tool_line_count == max_lines_per_tool:
                truncated_lines.append("... (工具输出内容已截断，仅显示前{}行)".format(max_lines_per_tool))
                tool_line_count += 1
        else:
            truncated_lines.append(line)
    
    return '\n'.join(truncated_lines)


def create_tool_wrapper(original_func, max_length, max_list_length=100, max_category_items=20):
    """创建工具函数包装器"""
    async def wrapped_func(*args, **kwargs):
        result = await original_func(*args, **kwargs)
        return limit_result_length(result, max_length, max_list_length, max_category_items)
    return wrapped_func

def limit_result_length(result, max_length, max_list_length=100, max_category_items=20):
    """
    限制返回内容长度，保持数据结构完整
    """
    try:
        if isinstance(result, str):
            if len(result) > max_length:
                return result[:max_length] + "...(内容已截断)"
            return result
        elif isinstance(result, dict):
            result = result.copy()
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    result[key] = limit_result_length(value, max_length, max_list_length, max_category_items)
                elif isinstance(value, str) and len(value) > max_length:
                    result[key] = value[:max_length] + "...(内容已截断)"
            if 'categories' in result and isinstance(result['categories'], dict):
                for category_key, category_value in result['categories'].items():
                    if isinstance(category_value, dict):
                        for subcategory_key, subcategory_value in category_value.items():
                            if isinstance(subcategory_value, list) and len(subcategory_value) > max_category_items:
                                truncated_list = subcategory_value[:max_category_items]
                                truncated_list.append({
                                    "id": "truncated",
                                    "name": f"...还有{len(subcategory_value) - max_category_items}个项目未显示...",
                                    "type": "info",
                                    "tags": {
                                        "note": f"原始列表包含{len(subcategory_value)}个项目，已截断以保持响应合理长度"
                                    }
                                })
                                result['categories'][category_key][subcategory_key] = truncated_list
            if 'content' in result:
                if isinstance(result['content'], str):
                    if len(result['content']) > max_length:
                        result['content'] = result['content'][:max_length] + "...(内容已截断)"
                elif isinstance(result['content'], list):
                    if len(result['content']) > 50:
                        result['content'] = result['content'][:50] + [
                            {"type": "text", "text": f"...(内容列表已截断，还有{len(result['content']) - 50}个项目)"}
                        ]
                    else:
                        total_length = 0
                        for item in result['content']:
                            if isinstance(item, dict) and 'text' in item:
                                text = item['text']
                                if isinstance(text, str):
                                    remaining_length = max_length - total_length
                                    if remaining_length <= 0:
                                        item['text'] = "...(内容已截断)"
                                        break
                                    elif len(text) > remaining_length:
                                        item['text'] = text[:remaining_length] + "...(内容已截断)"
                                    total_length += len(item['text'])
        elif isinstance(result, list):
            if len(result) > max_list_length:
                if _is_coordinate_list(result):
                    sampled_result = _sample_coordinate_list(result, max_list_length)
                    sampled_result.append({
                        "type": "info",
                        "text": f"...(坐标列表已采样，原始长度: {len(result)}, 采样后: {len(sampled_result)})"
                    })
                    result = sampled_result
                else:
                    result = _smart_truncate_list(result, max_list_length)
            else:
                for i, item in enumerate(result):
                    if isinstance(item, (dict, list)):
                        result[i] = limit_result_length(item, max_length, max_list_length, max_category_items)
                    elif isinstance(item, str) and len(item) > max_length:
                        result[i] = item[:max_length] + "...(内容已截断)"
        return result
    except Exception as e:
        logging.warning(f"限制返回内容长度时出错: {e}")
        return result


def _is_coordinate_list(lst):
    if not lst or not isinstance(lst, list):
        return False
    sample_size = min(5, len(lst))
    coordinate_count = 0
    for i in range(sample_size):
        item = lst[i]
        if (isinstance(item, list) and len(item) == 2 and 
            all(isinstance(coord, (int, float)) for coord in item)):
            coordinate_count += 1
        elif isinstance(item, dict) and 'location' in item:
            location = item['location']
            if (isinstance(location, list) and len(location) == 2 and 
                all(isinstance(coord, (int, float)) for coord in location)):
                coordinate_count += 1
    return coordinate_count / sample_size > 0.6


def _sample_coordinate_list(lst, max_length):
    if len(lst) <= max_length:
        return lst
    sampled = [lst[0]]
    interval = max(1, (len(lst) - 2) // (max_length - 2))
    for i in range(1, len(lst) - 1, interval):
        if len(sampled) >= max_length - 1:
            break
        sampled.append(lst[i])
    if len(sampled) < max_length and lst[-1] not in sampled:
        sampled.append(lst[-1])
    return sampled


def _smart_truncate_list(lst, max_length):
    if len(lst) <= max_length:
        return lst
    truncated = lst[:max_length - 1]
    truncated.append({
        "type": "info",
        "text": f"...(列表已截断，原始长度: {len(lst)}, 已截断: {len(lst) - max_length + 1})"
    })
    return truncated


class LimitedMCPClient:
    def __init__(self, config, max_response_length=5000, max_list_length=100, max_category_items=20):
        self.client = MultiServerMCPClient(config)
        self.max_length = max_response_length
        self.max_list_length = max_list_length
        self.max_category_items = max_category_items
    
    async def get_tools(self):
        tools = await self.client.get_tools()
        for tool in tools:
            original_func = tool.func
            tool.func = create_tool_wrapper(
                original_func, 
                self.max_length, 
                self.max_list_length, 
                self.max_category_items
            )
        return tools


def format_agent_step(step_message):
    if isinstance(step_message, HumanMessage):
        role_header = "================================== Human Input =================================="
        return f"\n{role_header}\n{step_message.content}\n"
    elif isinstance(step_message, AIMessage):
        role_header = "================================== AI Message ==================================="
        content = step_message.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        else:
            text = str(content)
        return f"\n{role_header}\n{text}\n"
    elif isinstance(step_message, ToolMessage):
        role_header = f"================================== Tool Output ({step_message.name}) =================================="
        content = step_message.content
        return f"\n{role_header}\n{content if isinstance(content, str) else _pretty_json(content)}\n"
    elif isinstance(step_message, dict) and step_message.get("type") == "tool_call":
        role_header = "================================== Tool Call ===================================="
        name = step_message.get("tool_name", "unknown_tool")
        args = step_message.get("tool_input", {})
        return f"\n{role_header}\n工具名: {name}\n参数: {_pretty_json(args)}\n"
    else:
        role_header = "================================== Unknown Message ================================"
        return f"\n{role_header}\n{getattr(step_message, 'content', '')}\n"


async def judge_task_completion(agent_behavior: str, task_description: str, expected_tools: list) -> tuple[bool, str, dict]:
    """
    使用 LLM 判断 Agent 是否成功完成任务，并返回 (是否完成, 原因, 完整JSON)
    """
    api_key = "sk-prcsibeysdxgisruwtaqptfiysnlwzfzxzkrxqffisjzkngf"
    api_base = os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1")

    if not api_key:
        raise RuntimeError("请为裁判 LLM 设置 OPENAI_API_KEY 环境变量")

    judge_llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model="deepseek-ai/DeepSeek-V3",
        temperature=0.0
    )

    prompt_template = """
    你是一个专业的 AI Agent 任务评估员。你的任务是根据 Agent 的实际行为，判断其是否成功完成了指定的任务。

    请严格按照以下信息进行判断：
    1.  **任务描述**: {task_description}
    2.  **预期工具**: {expected_tools}
    3.  **Agent 的实际行为**: {agent_behavior}

    请判断"Agent 的实际行为"是否表明任务已成功完成，并特别注意是否因为MCP工具异常导致任务失败。

    判断标准：
    1. 如果任务成功完成，返回 "完成"
    2. 如果因为MCP工具异常（如工具无法加载、工具调用失败、工具返回错误等）导致任务失败，返回 "未完成" 并在原因中说明是MCP异常
    3. 如果Agent本身执行有问题（如没有调用预期工具、逻辑错误等）导致任务失败，返回 "未完成" 并在原因中说明是Agent问题
    4. 其他原因导致的失败，返回 "未完成"

    你的回答必须严格按照以下 JSON 格式：
    {{
        "result": "完成" 或 "未完成",
        "reason": "具体原因说明",
        "failure_type": "success" 或 "mcp_error" 或 "agent_error" 或 "other"
    }}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | judge_llm | StrOutputParser()
    
    try:
        response = await chain.ainvoke({
            "agent_behavior": agent_behavior,
            "task_description": task_description,
            "expected_tools": ", ".join(expected_tools) if expected_tools else "无特定工具要求"
        })
        log_and_echo("\n--- 裁判模型分析 ---\n裁判模型输出: " + str(response).strip())
        try:
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            result = json.loads(cleaned_response)
            is_completed = result.get("result", "") == "完成"
            reason = result.get("reason", "无具体原因")
            failure_type = result.get("failure_type", "unknown")
            if failure_type != "success":
                reason = f"[{failure_type}] {reason}"
            return is_completed, reason, result
        except json.JSONDecodeError:
            text = str(response).strip()
            norm = re.sub(r"\s+", "", text)
            if norm == "完成":
                json_result = {"result": "完成", "reason": "任务已完成", "failure_type": "success"}
                return True, "任务已完成", json_result
            if norm == "未完成":
                json_result = {"result": "未完成", "reason": "任务未完成", "failure_type": "other"}
                return False, "任务未完成", json_result
            if "未完成" in text:
                json_result = {"result": "未完成", "reason": text, "failure_type": "other"}
                return False, text, json_result
            if "完成" in text:
                json_result = {"result": "完成", "reason": text, "failure_type": "success"}
                return True, text, json_result
            json_result = {"result": "未完成", "reason": f"裁判输出不规范：{text}", "failure_type": "other"}
            return False, f"裁判输出不规范：{text}", json_result
    except Exception as e:
        logging.exception("裁判模型调用失败: %s", e)
        json_result = {"result": "未完成", "reason": f"裁判模型调用失败: {str(e)}", "failure_type": "other"}
        return False, f"裁判模型调用失败: {str(e)}", json_result


def load_mcp_configs_from_live_config(live_config_path):
    with open(live_config_path, "r", encoding="utf-8") as f:
        live_configs = json.load(f)
    merged_config = {}
    for item in live_configs:
        if "config" in item and "mcpServers" in item["config"]:
            servers = item["config"]["mcpServers"]
            merged_config.update(servers)
    return merged_config


def load_tool_to_mcp_mapping(tool2mcp_path):
    with open(tool2mcp_path, "r", encoding="utf-8") as f:
        tool2mcp_data = json.load(f)
    
    tool_to_mcp = {}
    mcp_configs = {}
    
    for item in tool2mcp_data:
        if "config" in item and "mcpServers" in item["config"]:
            servers = item["config"]["mcpServers"]
            mcp_configs.update(servers)
            server_name = list(servers.keys())[0] if servers else None
            if server_name and "tools" in item:
                server_tools = item["tools"].get(server_name, {})
                for tool_item in server_tools.get("tools", []):
                    tool_name = tool_item.get("name")
                    if tool_name:
                        tool_to_mcp[tool_name] = server_name
    return tool_to_mcp, mcp_configs


async def fetch_server_tool_names(server_key: str, server_cfg: dict) -> set[str]:
    """单独连接一个 server，返回其当前暴露的工具名集合"""
    client = MultiServerMCPClient({server_key: server_cfg})
    try:
        tools = await client.get_tools()
        return {t.name for t in tools}
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()


async def main(dataset, use_mytool: bool = True):
    setup_run_logger()

    all_mcp_config = load_mcp_configs_from_live_config("./configs/live_mcp.json")
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping("./configs/tool2mcp.json")

    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(".py"):
            tool["args"][0] = os.path.abspath(tool["args"][0])

    api_key = "e1322f288a304f1a87cdd0fc7b517030.AiVpxsRFOCy7VAdg"
    api_base = "https://open.bigmodel.cn/api/paas/v4/"
    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model="glm-4.5",
        streaming=True,
        temperature=0.7
    )

    results_summary = []

    for task in dataset:
        task_id = task["id"]
        task_desc = task["description"]
        user_prompt = task["input"]
        expected_tools = task["expected_tools"]

        task_start_time = time.time()
        log_and_echo(f"=============== 运行任务 {task_id}（{task_desc}） ===============")

        # === 构造 filtered_config（包含 expected 工具 + 可选 mytool）===
        filtered_config = {}
        required_mcp_servers = set()

        if expected_tools:
            for tool_name in expected_tools:
                if tool_name in tool_to_mcp:
                    mcp_server_name = tool_to_mcp[tool_name]
                    required_mcp_servers.add(mcp_server_name)

        mytool_server_key = "mytool"
        mytool_server_path = "./tools/myTool.py"
        if use_mytool:
            filtered_config[mytool_server_key] = {
                "command": "python",
                "args": [os.path.abspath(mytool_server_path)],
                "transport": "stdio"
            }

        for server_name in required_mcp_servers:
            if server_name in mcp_configs:
                filtered_config[server_name] = mcp_configs[server_name].copy()
                filtered_config[server_name].setdefault("transport", "stdio")
                if (filtered_config[server_name]["command"] == "python" and
                    filtered_config[server_name].get("args") and
                    filtered_config[server_name]["args"][0].endswith(".py")):
                    filtered_config[server_name]["args"][0] = os.path.abspath(filtered_config[server_name]["args"][0])

        log_and_echo("🧪 工具加载: " + str(list(filtered_config.keys())))

        # === 动态获取 mytool 的工具名集合 ===
        mytool_tool_names: set[str] = set()
        if use_mytool and mytool_server_key in filtered_config:
            try:
                mytool_tool_names = await fetch_server_tool_names(mytool_server_key, filtered_config[mytool_server_key])
                log_and_echo(f"mytool 工具清单: {sorted(mytool_tool_names)}")
            except Exception as e:
                log_and_echo(f"⚠️ 获取 mytool 工具名失败，将无法区分其调用：{e}")
                mytool_tool_names = set()

        # --- 加载 MCP 工具（容错） ---
        try:
            client = MultiServerMCPClient(filtered_config)
            tools = await client.get_tools()
        except Exception as e:
            log_and_echo(f"❌ 加载 MCP 工具失败: {e}")
            task_end_time = time.time()
            task_execution_time = task_end_time - task_start_time
            task_execution_time_formatted = f"{task_execution_time:.2f}秒"
            
            results_summary.append({
                "task_id": task_id,
                "description": task_desc,
                "input": user_prompt,
                "expected_tools": expected_tools,
                "correct_behavior": task.get("correct_behavior", "N/A"),
                "wrong_behavior": task.get("wrong_behavior", "N/A"),
                "agent_final_response": "MCP 工具加载失败",
                "tool_calls": [],
                "task_completed": False,
                "completion_reason": {
                    "result": "未完成",
                    "reason": f"MCP 工具加载失败: {e.__class__.__name__}",
                    "failure_type": "mcp_error"
                },
                "failure_reason": f"MCP load error: {e.__class__.__name__}",
                "execution_time": task_execution_time_formatted,
                "execution_time_seconds": task_execution_time,
                "total_tool_calls": 0,
                "mytool_calls": 0,
                "mytool_enabled": bool(use_mytool),
                "tool_name_duplicate_warning": False,
            })
            continue

        # --- 创建 Agent 并行（容错） ---
        final_response = ""
        tool_calls_brief = []
        tool_interactions = []
        try:
            agent = create_react_agent(llm, tools, checkpointer=MemorySaver())
            config = {"recursion_limit": 100, "configurable": {"thread_id": f"test-{task_id}"}}
            user_input = {"role": "user", "content": user_prompt}

            async for step in agent.astream({"messages": [user_input]}, config, stream_mode="values"):
                last_message = step["messages"][-1]
                pretty = format_agent_step(last_message)
                log_and_echo(pretty)

                if isinstance(last_message, AIMessage):
                    content = last_message.content
                    if isinstance(content, str):
                        final_response = content
                    elif isinstance(content, list):
                        final_response = "\n".join(
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                        )
                    else:
                        final_response = str(content)
                    tool_interactions.append({
                        "type": "ai_message",
                        "content": final_response
                    })

                    tool_calls = getattr(last_message, "tool_calls", None) or last_message.additional_kwargs.get("tool_calls", [])
                    for tc in tool_calls or []:
                        fn = (tc.get("function") or {})
                        name = fn.get("name") or tc.get("name", "unknown_tool")
                        args = fn.get("arguments") or tc.get("args") or {}
                        try:
                            if isinstance(args, str):
                                args = json.loads(args)
                        except Exception:
                            pass
                        tool_calls_brief.append({"tool": name, "args": args})
                        tool_call_msg = {"type": "tool_call", "tool_name": name, "tool_input": args}
                        tc_pretty = format_agent_step(tool_call_msg)
                        log_and_echo(tc_pretty)
                        tool_interactions.append({
                            "type": "tool_call",
                            "tool_name": name,
                            "arguments": args
                        })

                elif isinstance(last_message, ToolMessage):
                    tool_output_content = last_message.content
                    if isinstance(tool_output_content, str):
                        tool_output_text = tool_output_content
                    elif isinstance(tool_output_content, list):
                        tool_output_text = "\n".join(
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in tool_output_content
                        )
                    else:
                        tool_output_text = str(tool_output_content)
                    tool_interactions.append({
                        "type": "tool_output",
                        "tool_name": last_message.name,
                        "output": tool_output_text
                    })

                elif isinstance(last_message, dict) and last_message.get("type") == "tool_call":
                    fn = (last_message.get("function") or {})
                    name = fn.get("name") or last_message.get("name", "unknown_tool")
                    args = fn.get("arguments") or last_message.get("args") or {}
                    try:
                        if isinstance(args, str):
                            args = json.loads(args)
                    except Exception:
                        pass
                    tool_calls_brief.append({"tool": name, "args": args})
                    tool_interactions.append({
                        "type": "tool_call",
                        "tool_name": name,
                        "arguments": args
                    })

        except Exception as e:
            log_and_echo(f"❌ 运行代理失败: {e}")
            task_end_time = time.time()
            task_execution_time = task_end_time - task_start_time
            task_execution_time_formatted = f"{task_execution_time:.2f}秒"
            results_summary.append({
                "task_id": task_id,
                "description": task_desc,
                "input": user_prompt,
                "expected_tools": expected_tools,
                "correct_behavior": task.get("correct_behavior", "N/A"),
                "wrong_behavior": task.get("wrong_behavior", "N/A"),
                "agent_final_response": f"Agent 运行失败: {e}",
                "tool_calls": [],
                "task_completed": False,
                "completion_reason": {
                    "result": "未完成",
                    "reason": f"Agent 运行失败: {e.__class__.__name__}",
                    "failure_type": "agent_error"
                },
                "failure_reason": f"Agent run error: {e.__class__.__name__}",
                "execution_time": task_execution_time_formatted,
                "execution_time_seconds": task_execution_time,
                "total_tool_calls": 0,
                "mytool_calls": 0,
                "mytool_enabled": bool(use_mytool),
                "tool_name_duplicate_warning": False,
            })
            continue

        # === 任务完成度判断 ===
        is_task_completed = False
        completion_reason = "缺少必要信息"
        completion_json = {"result": "未知", "reason": "缺少必要信息", "failure_type": "unknown"}
        if final_response and task_desc:
            truncated_response = truncate_tool_outputs(final_response, max_lines_per_tool=10)
            is_task_completed, completion_reason, completion_json = await judge_task_completion(
                agent_behavior=truncated_response,
                task_description=task_desc,
                expected_tools=expected_tools
            )
        else:
            log_and_echo("⚠️  跳过任务完成度判断（缺少必要信息）")

        # === 工具调用统计 ===
        total_tool_calls = sum(1 for x in tool_interactions if x.get("type") == "tool_call")

        def _is_mytool_call(x) -> bool:
            if x.get("type") != "tool_call":
                return False
            name = x.get("tool_name")
            return bool(name) and (name in mytool_tool_names)

        mytool_calls = sum(1 for x in tool_interactions if _is_mytool_call(x))

        try:
            all_tool_names_list = [t.name for t in tools]
            has_duplicates = len(all_tool_names_list) != len(set(all_tool_names_list))
        except Exception:
            has_duplicates = False

        # 计算任务执行时间
        task_end_time = time.time()
        task_execution_time = task_end_time - task_start_time
        task_execution_time_formatted = f"{task_execution_time:.2f}秒"

        results_summary.append({
            "task_id": task_id,
            "description": task_desc,
            "input": user_prompt,
            "expected_tools": expected_tools,
            "correct_behavior": task.get("correct_behavior", "N/A"),
            "wrong_behavior": task.get("wrong_behavior", "N/A"),
            "agent_final_response": final_response,
            "tool_calls": tool_calls_brief,
            "tool_interactions": tool_interactions,
            "task_completed": is_task_completed,
            "completion_reason": completion_json,
            "execution_time": task_execution_time_formatted,
            "execution_time_seconds": task_execution_time,
            "total_tool_calls": total_tool_calls,
            "mytool_calls": mytool_calls,
            "mytool_enabled": bool(use_mytool),
            "tool_name_duplicate_warning": bool(has_duplicates),
        })

    # === 汇总结果 ===
    total_tasks = len(dataset)
    completed_tasks = sum(1 for r in results_summary if r["task_completed"])
    completion_rate = (0 if total_tasks == 0 else completed_tasks / total_tasks * 100)
    overall_total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results_summary)
    overall_mytool_calls = sum(r.get("mytool_calls", 0) for r in results_summary)

    final_report = {
        "run_timestamp": datetime.now().isoformat(),
        "overall_statistics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": f"{completion_rate:.2f}%",
            "total_tool_calls": overall_total_tool_calls,
            "mytool_calls": overall_mytool_calls,
        },
        "task_details": results_summary
    }

    with open(RESULT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print("\n================= 所有任务运行完毕 =================\n")
    print(f"📊 任务完成率: {completion_rate:.2f}% ({completed_tasks}/{total_tasks})")
    print(f"📊 总工具调用次数: {overall_total_tool_calls}，其中 mytool: {overall_mytool_calls}")
    print(f"📄 结果 JSON 路径: {RESULT_JSON_FILE}")
    print(f"📝 运行日志路径: {RUN_LOG_FILE}")
    logging.info("Run finished. Results written to %s; logs at %s", RESULT_JSON_FILE, RUN_LOG_FILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-mytool", action="store_true", help="启用 mytool MCP server")
    args = parser.parse_args()

    dataset = []
    task_dict = {}
    try:
        with open("./datasets/test_prompts.json", "r", encoding="utf-8") as f:
            test_prompts_data = json.load(f)
            for item in test_prompts_data:
                task_id = item.get("task_id", "")
                tools_str = item.get("Annotator Metadata", {}).get("Tools", "")
                expected_tools = []
                if tools_str:
                    tools_list = [t.strip() for t in tools_str.replace("1.", "").replace("2.", "").replace("3.", "").replace("4.", "").replace("5.", "").replace("6.", "").split("\n") if t.strip()]
                    expected_tools = [t for t in tools_list if t]
                if task_id and task_id in task_dict:
                    steps_desc = item.get("Annotator Metadata", {}).get("Steps", "").lower()
                    if expected_tools:
                        if ("geocode" in steps_desc or "parking" in steps_desc or "nearby" in steps_desc) and \
                           (any(tool in expected_tools for tool in ["geocode_address", "find_parking_facilities", "find_nearby_places", "reverse_geocode"])):
                            task_dict[task_id]["expected_tools"] = expected_tools
                        elif "valorant" in steps_desc and "valorant" in tools_str:
                            task_dict[task_id]["expected_tools"] = expected_tools
                else:
                    task_data = {
                        "id": task_id or f"task-{len(dataset)+1}",
                        "description": item.get("Question", ""),
                        "input": item.get("Question", ""),
                        "expected_tools": expected_tools,
                        "category": item.get("category", ""),
                        "correct_behavior": "N/A",
                        "wrong_behavior": "N/A"
                    }
                    dataset.append(task_data)
                    if task_id:
                        task_dict[task_id] = task_data
    except FileNotFoundError:
        print("警告: 未找到数据集文件 ./datasets/test_prompts.json")
    except Exception as e:
        print(f"加载 ./datasets/test_prompts.json 时出错: {e}")
    
    if dataset:
        asyncio.run(main(dataset, use_mytool=args.use_mytool))
    else:
        print("错误: 没有找到任何有效的数据集文件")
