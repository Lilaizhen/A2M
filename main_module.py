import asyncio
import json
import os
import time
import re
import sys
from datetime import datetime
import argparse
from random import random

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_community.callbacks.manager import get_openai_callback

# 加载自定义模块
from src.utils.logging_config import setup_run_logger, log_and_echo, task_log_context
from src.utils.tool_functions import truncate_tool_outputs, _now, _as_text, render_behavior_from_trace
from src.mcp_client.client import LimitedMCPClient
from src.defenses import FidesGuard
from src.agents.agent_utils import format_agent_step
from src.evaluators.task_evaluator import judge_task_completion
from src.data_loaders.data_loader import (
    load_mcp_configs_from_live_config,
    load_tool_to_mcp_mapping,
    fetch_server_tool_names,
    load_dataset,
)
from src.core.executor import TaskExecutor
from src.utils.task_isolation import TaskIsolationManager
from src.attacks.scoring.fitness_calculator import FitnessCalculator, AttackType

load_dotenv()  # 加载 .env 文件中的环境变量


def _convert_relative_paths_in_text(text):
    """
    在文本中查找类似 "./path/to/file" 的相对路径并转换为绝对路径
    仅转换以 ./ 或 ../ 开头的路径
    """
    if not text or not isinstance(text, str):
        return text

    pattern = r'(["\']?)(\.{1,2}/[^\s"\']+)["\']?'

    def replace_path(match):
        quote = match.group(1)
        path = match.group(2)
        if path.startswith("./") or path.startswith("../"):
            try:
                abs_path = os.path.abspath(path)
                return f"{quote}{abs_path}{quote}"
            except Exception:
                return match.group(0)
        return match.group(0)

    return re.sub(pattern, replace_path, text)


# --- 全局配置 ---
RESULTS_DIR = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
os.makedirs(RESULTS_DIR, exist_ok=True)

RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")

# 可选：限制单条工具输出写入轨迹的最大字符数，避免结果过大
MAX_TOOL_OUTPUT_CHARS = 8000


# ============ 重试工具函数（新增） ============
def _is_transient_error(e: Exception) -> bool:
    s = (str(e) or "").lower()
    return isinstance(e, (asyncio.TimeoutError, ConnectionError, OSError)) or any(
        x in s
        for x in [
            "econnreset",
            "temporary failure",
            "tls",
            "broken pipe",
            "connection aborted",
            "timed out",
            "proxy",
            "eoferror",
            "connecterror",
            "connecttimeout",
        ]
    )


def _is_agent_soft_error(e: Exception) -> bool:
    s = (str(e) or "").lower()
    return any(
        x in s
        for x in [
            "recursion limit",
            "graphrecursionerror",
            "recursionerror",
            "prompt exceed max tokens",
            "promptexceedmaxtokens",
            "error code: 511",
            "code': '511'",
        ]
    )


async def retry_async(op, *, tries=4, base=0.5, factor=2.0, max_delay=8.0, name="op"):
    """
    对异步操作做指数退避 + 抖动的重试。
    op: 零参可调用，返回 coroutine。
    """
    last = None
    for i in range(tries):
        try:
            return await op()
        except Exception as e:
            last = e
            transient = _is_transient_error(e)
            if i == tries - 1 or not transient:
                raise
            delay = min(max_delay, base * (factor ** i)) * (0.5 + random())
            log_and_echo(
                f"↻ 重试 {name} ({i+1}/{tries-1})，原因：{e.__class__.__name__}: {str(e)[:120]}，等待 {delay:.2f}s"
            )
            await asyncio.sleep(delay)
    raise last
# ============================================


def _safe_task_filename(index: int, task_id: str) -> str:
    safe_task_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id))
    return f"{index:03d}_{safe_task_id}.json"


def _atomic_write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)


def _remap_annotated_data_paths(text: str, task_annotated_data_path: str) -> str:
    if not text or not isinstance(text, str):
        return text
    original_annotated_data_path = os.path.abspath(os.path.join(os.getcwd(), "annotated_data"))
    result = text.replace(original_annotated_data_path, task_annotated_data_path)
    result = result.replace("./annotated_data", task_annotated_data_path)
    return result


def _remap_task_paths(text: str, task_annotated_data_path: str, *, remap_repo_root: bool = False) -> str:
    if not text or not isinstance(text, str):
        return text
    repo_root = os.path.abspath(os.getcwd())
    process_root = os.path.dirname(task_annotated_data_path)
    original_annotated_data_path = os.path.join(repo_root, "annotated_data")
    placeholder = "__MCP_BENCH_TASK_ANNOTATED_DATA__"
    result = text.replace(original_annotated_data_path, placeholder)
    result = result.replace("./annotated_data", placeholder)
    if remap_repo_root:
        result = result.replace(repo_root, process_root)
    result = result.replace(placeholder, task_annotated_data_path)
    return result


def _remap_paths_in_object(value, task_annotated_data_path: str, *, remap_repo_root: bool = False):
    if isinstance(value, str):
        return _remap_task_paths(value, task_annotated_data_path, remap_repo_root=remap_repo_root)
    if isinstance(value, list):
        return [_remap_paths_in_object(item, task_annotated_data_path, remap_repo_root=remap_repo_root) for item in value]
    if isinstance(value, dict):
        return {
            key: _remap_paths_in_object(item, task_annotated_data_path, remap_repo_root=remap_repo_root)
            for key, item in value.items()
        }
    return value


def _failed_task_result(task: dict, reason: str, failure_type: str = "system_error") -> dict:
    return {
        "task_id": task.get("id", "unknown"),
        "input": task.get("input", ""),
        "expected_tools": task.get("expected_tools", []),
        "agent_final_response": reason,
        "task_completed": False,
        "completion_reason": {
            "result": "未完成",
            "reason": reason,
            "failure_type": failure_type,
        },
        "execution_time_seconds": 0,
        "total_tool_calls": 0,
        "mytool_calls": 0,
        "token_usage": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        },
        "action_trace": [],
    }


async def main(
    dataset,
    attack: bool = True,
    attack_dataset_path: str = None,
    attack_scenario: str = "resource_waste",
    model_name: str = None,
    judge_model: str = None,
    dataset_type: str = "all",
    run_args: dict | None = None,
    run_argv: list[str] | None = None,
    concurrency: int = 1,
    judge_concurrency: int | None = None,
    agent_rpm_limit: float | None = None,
    resume: bool = False,
    results_dir: str | None = None,
    keep_isolation: bool = False,
    defense: str = "none",
    fides_same_tool_same_args_limit: int = 3,
    fides_max_total_tool_calls: int = 35,
    fides_label_outputs: bool = True,
    fides_block_unsafe_path_writes: bool = True,
):
    isolation_manager = TaskIsolationManager()

    # 重试执行单个任务的函数
    async def _run_task_with_retry(
        task_id, task_desc, user_prompt, expected_tools, attack, attack_dataset_path,
        attack_tool_mapping, mcp_configs, tool_to_mcp, proxy_settings, extra_mcp_configs,
        llm, mytool_tool_names, judge_semaphore=None, keep_isolation=False,
        defense="none", fides_same_tool_same_args_limit=3,
        fides_max_total_tool_calls=35, fides_label_outputs=True,
        fides_block_unsafe_path_writes=True,
    ):
        max_retries = 5
        original_task_desc = task_desc
        original_user_prompt = user_prompt
        last_defense_summary = None

        def _with_defense(result, guard=None):
            nonlocal last_defense_summary
            if defense != "fides":
                return result
            if guard is not None:
                last_defense_summary = guard.summary()
            result["defense"] = last_defense_summary or {
                "name": "fides",
                "policy": "scenario_agnostic_untrusted_tool_output_and_runtime_limits",
                "blocked_count": 0,
                "events": [],
            }
            return result

        for attempt in range(max_retries):
            task_start_time = time.time()
            if attempt > 0:
                log_and_echo(f"=============== 重试运行任务 {task_id}（{task_desc}） [尝试 {attempt + 1}/{max_retries}] ===============")

            process_id = None
            task_annotated_data_path = None
            limited = None
            fides_guard = None
            try:
                process_id, _, task_annotated_data_path = isolation_manager.create_process_isolation_dir(task_id)
                if defense == "fides":
                    fides_guard = FidesGuard(
                        task_annotated_data_path=task_annotated_data_path,
                        repo_root=os.getcwd(),
                        same_tool_same_args_limit=fides_same_tool_same_args_limit,
                        max_total_tool_calls=fides_max_total_tool_calls,
                        label_tool_outputs=fides_label_outputs,
                        block_unsafe_path_writes=fides_block_unsafe_path_writes,
                    )
                task_desc = _remap_annotated_data_paths(original_task_desc, task_annotated_data_path)
                user_prompt = _remap_annotated_data_paths(original_user_prompt, task_annotated_data_path)
                if attempt == 0:
                    log_and_echo(f"🔧 使用任务隔离目录: {task_annotated_data_path}")

                # === 构造 filtered_config（包含 expected 工具 + 可选 mytool + 额外配置）===
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
                        "transport": "stdio",
                    }
                    if (
                        attack_dataset_path
                        and task_id in attack_tool_mapping
                        and attack_tool_mapping[task_id]
                    ):
                        attack_tool = attack_tool_mapping[task_id][0]
                        attack_tool = _remap_paths_in_object(
                            attack_tool,
                            task_annotated_data_path,
                            remap_repo_root=(attack_scenario == AttackType.TASK_FAILURE.value),
                        )
                        config_json = json.dumps(attack_tool, ensure_ascii=False)
                        mytool_config["args"].extend([config_json])
                    filtered_config[mytool_server_key] = mytool_config

                for server_name in required_mcp_servers:
                    if server_name in mcp_configs:
                        filtered_config[server_name] = mcp_configs[server_name].copy()
                        filtered_config[server_name].setdefault("transport", "stdio")
                        if (
                            filtered_config[server_name]["command"] == "python"
                            and filtered_config[server_name].get("args")
                            and filtered_config[server_name]["args"][0].endswith(".py")
                        ):
                            filtered_config[server_name]["args"][0] = os.path.abspath(
                                filtered_config[server_name]["args"][0]
                            )

                        if proxy_settings:
                            if "env" not in filtered_config[server_name]:
                                filtered_config[server_name]["env"] = {}
                            for key, value in proxy_settings.items():
                                if key not in filtered_config[server_name]["env"]:
                                    filtered_config[server_name]["env"][key] = value

                # 添加额外的MCP配置（避免重复加载）
                for server_name, server_config in extra_mcp_configs.items():
                    if server_name not in filtered_config:
                        filtered_config[server_name] = server_config.copy()
                        filtered_config[server_name].setdefault("transport", "stdio")
                        if (
                            filtered_config[server_name]["command"] == "python"
                            and filtered_config[server_name].get("args")
                            and filtered_config[server_name]["args"][0].endswith(".py")
                        ):
                            filtered_config[server_name]["args"][0] = os.path.abspath(
                                filtered_config[server_name]["args"][0]
                            )

                        if proxy_settings:
                            if "env" not in filtered_config[server_name]:
                                filtered_config[server_name]["env"] = {}
                            for key, value in proxy_settings.items():
                                if key not in filtered_config[server_name]["env"]:
                                    filtered_config[server_name]["env"][key] = value

                filtered_config, _ = isolation_manager.generate_mcp_config_for_process(
                    filtered_config,
                    task_annotated_data_path,
                    process_id,
                )

                if attempt == 0:
                    log_and_echo("🧪 工具加载: " + str(list(filtered_config.keys())))

                # === 动态获取 mytool 的工具名集合（加重试）===
                if attack and mytool_server_key in filtered_config and attempt == 0:
                    try:
                        mytool_tool_names_inner = await retry_async(
                            lambda: fetch_server_tool_names(
                                mytool_server_key,
                                filtered_config[mytool_server_key],
                                MultiServerMCPClient,
                            ),
                            tries=3,
                            base=0.6,
                            factor=2.0,
                            max_delay=6.0,
                            name="fetch_server_tool_names",
                        )
                        log_and_echo(f"mytool 工具清单: {sorted(mytool_tool_names_inner)}")
                    except Exception as e:
                        log_and_echo(f"⚠️ 获取 mytool 工具名失败，将无法区分其调用：{e}")
                        mytool_tool_names_inner = set()

                # --- 加载 MCP 工具（LimitedMCPClient，带重试）---
                try:
                    limited = LimitedMCPClient(
                        filtered_config,
                        max_response_length=5000,
                        max_list_length=100,
                        max_category_items=20,
                        timeout=30,
                        fides_guard=fides_guard,
                    )
                    tools = await retry_async(
                        lambda: limited.get_tools(),
                        tries=4,
                        base=0.8,
                        factor=2.0,
                        max_delay=8.0,
                        name="limited.get_tools",
                    )
                except Exception as e:
                    log_and_echo(f"❌ 加载 MCP 工具失败: {e}")
                    if attempt < max_retries - 1:
                        log_and_echo(f"[任务 {task_id}] 第 {attempt + 1} 次尝试遇到 MCP 工具加载失败，正在重试...")
                        continue
                    else:
                        task_end_time = time.time()
                        task_execution_time = task_end_time - task_start_time

                        return _with_defense({
                            "task_id": task_id,
                            "input": user_prompt,
                            "expected_tools": expected_tools,
                            "agent_final_response": "MCP 工具加载失败",
                            "task_completed": False,
                            "completion_reason": {
                                "result": "未完成",
                                "reason": f"MCP 工具加载失败: {e.__class__.__name__}",
                                "failure_type": "mcp_error",
                            },
                            "execution_time_seconds": task_execution_time,
                            "total_tool_calls": 0,
                            "mytool_calls": 0,
                            "token_usage": {
                                "total_tokens": 0,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                            },
                            "action_trace": [
                                {"ts": _now(), "type": "user_input", "content": user_prompt}
                            ],
                        }, fides_guard)

                # --- 创建 Agent 并行（容错） ---
                final_response = ""
                action_trace = []  # 行动轨迹
                token_usage = {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }

                action_trace.append({"ts": _now(), "type": "user_input", "content": user_prompt})

                agent_error = None
                try:
                    agent = create_react_agent(llm, tools, checkpointer=MemorySaver())
                    config = {
                        "recursion_limit": 40,
                        "configurable": {"thread_id": f"test-{task_id}"},
                    }
                    user_input = {"role": "user", "content": user_prompt}

                    with get_openai_callback() as cb:
                        current_tool_execution = None
                        tool_lock = asyncio.Lock()

                        async def _drain_stream():
                            nonlocal final_response, action_trace, current_tool_execution
                            async for step in agent.astream(
                                {"messages": [user_input]}, config, stream_mode="values"
                            ):
                                last_message = step["messages"][-1]
                                pretty = format_agent_step(last_message)
                                log_and_echo(pretty)

                                # 1) 工具输出
                                if isinstance(last_message, ToolMessage):
                                    tool_output_text = _as_text(last_message.content)
                                    if (
                                        isinstance(tool_output_text, str)
                                        and len(tool_output_text) > MAX_TOOL_OUTPUT_CHARS
                                    ):
                                        tool_output_text = (
                                            tool_output_text[:MAX_TOOL_OUTPUT_CHARS]
                                            + "...(内容已截断)"
                                        )
                                    action_trace.append(
                                        {
                                            "ts": _now(),
                                            "type": "tool_output",
                                            "tool": last_message.name,
                                            "output": tool_output_text,
                                        }
                                    )
                                    current_tool_execution = None
                                    continue

                                # 2) AI 消息 + 工具调用
                                if isinstance(last_message, AIMessage):
                                    content_text = _as_text(last_message.content).strip()
                                    if content_text:
                                        final_response = content_text
                                        action_trace.append(
                                            {
                                                "ts": _now(),
                                                "type": "ai_message",
                                                "content": content_text,
                                            }
                                        )

                                    tool_calls = getattr(last_message, "tool_calls", None) or last_message.additional_kwargs.get(
                                        "tool_calls", []
                                    )

                                    async with tool_lock:
                                        while current_tool_execution is not None:
                                            await asyncio.sleep(0.1)

                                        if tool_calls:
                                            tc = tool_calls[0]
                                            fn = (tc.get("function") or {})
                                            name = fn.get("name") or tc.get("name", "unknown_tool")
                                            args = fn.get("arguments") or tc.get("args") or {}
                                            try:
                                                if isinstance(args, str):
                                                    args = json.loads(args)
                                            except Exception:
                                                pass
                                            action_trace.append(
                                                {
                                                    "ts": _now(),
                                                    "type": "tool_call",
                                                    "tool": name,
                                                    "args": args,
                                                }
                                            )
                                            tool_call_msg = {
                                                "type": "tool_call",
                                                "tool_name": name,
                                                "tool_input": args,
                                            }
                                            tc_pretty = format_agent_step(tool_call_msg)
                                            log_and_echo(tc_prety if (tc_prety := tc_pretty) else tc_pretty)  # 兼容局部变量引用
                                            current_tool_execution = name
                                    continue

                                # 3) 兜底：dict 形式的 tool_call
                                if isinstance(last_message, dict) and last_message.get("type") == "tool_call":
                                    fn = (last_message.get("function") or {})
                                    name = fn.get("name") or last_message.get("name", "unknown_tool")
                                    args = fn.get("arguments") or last_message.get("args") or {}
                                    try:
                                        if isinstance(args, str):
                                            args = json.loads(args)
                                    except Exception:
                                        pass
                                    async with tool_lock:
                                        while current_tool_execution is not None:
                                            await asyncio.sleep(0.1)

                                        action_trace.append(
                                            {
                                                "ts": _now(),
                                                "type": "tool_call",
                                                "tool": name,
                                                "args": args,
                                            }
                                        )
                                        tool_call_msg = {
                                            "type": "tool_call",
                                            "tool_name": name,
                                            "tool_input": args,
                                        }
                                        tc_pretty = format_agent_step(tool_call_msg)
                                        log_and_echo(tc_prety if (tc_prety := tc_pretty) else tc_pretty)
                                        current_tool_execution = name
                                    return

                        async def _run_stream_once():
                            try:
                                await asyncio.wait_for(_drain_stream(), timeout=500)
                            except asyncio.TimeoutError:
                                log_and_echo("Agent 流式执行超时（>500s）")
                                action_trace.append(
                                    {
                                        "ts": _now(),
                                        "type": "ai_message",
                                        "content": "Agent 执行超时（>500s）",
                                    }
                                )

                        # 整体流式执行再加一层重试（抗瞬断）
                        try:
                            await retry_async(
                                _run_stream_once,
                                tries=5,
                                base=1.0,
                                factor=2.0,
                                max_delay=5.0,
                                name="agent.stream",
                            )
                        except Exception as e:
                            if _is_agent_soft_error(e):
                                agent_error = str(e)
                                action_trace.append(
                                    {
                                        "ts": _now(),
                                        "type": "ai_message",
                                        "content": f"Agent stopped: {agent_error}",
                                    }
                                )
                            else:
                                raise

                        token_usage = {
                            "total_tokens": cb.total_tokens,
                            "prompt_tokens": cb.prompt_tokens,
                            "completion_tokens": cb.completion_tokens,
                        }

                except Exception as e:
                    log_and_echo(f"❌ 运行代理失败: {e}")
                    if attempt < max_retries - 1:
                        log_and_echo(f"[任务 {task_id}] 第 {attempt + 1} 次尝试遇到 Agent 运行失败，正在重试...")
                        continue
                    else:
                        task_end_time = time.time()
                        task_execution_time = task_end_time - task_start_time
                        return _with_defense({
                            "task_id": task_id,
                            "input": user_prompt,
                            "expected_tools": expected_tools,
                            "agent_final_response": f"Agent 运行失败: {e}",
                            "task_completed": False,
                            "completion_reason": {
                                "result": "未完成",
                                "reason": f"Agent 运行失败: {e.__class__.__name__}",
                                "failure_type": "system_error",
                            },
                            "execution_time_seconds": task_execution_time,
                            "total_tool_calls": sum(1 for x in action_trace if x.get("type") == "tool_call"),
                            "mytool_calls": sum(
                                1
                                for x in action_trace
                                if x.get("type") == "tool_call" and x.get("tool") in mytool_tool_names
                            ),
                            "token_usage": {
                                "total_tokens": 0,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                            },
                            "action_trace": action_trace,
                        }, fides_guard)

                # === 检查 agent 行为轨迹的最后一个步骤是否是 AI 输出的信息 ===
                def _check_last_step_is_ai_message(trace):
                    """检查轨迹的最后一个步骤是否是 AI 消息"""
                    if not trace:
                        return False
                    # 获取最后一个步骤
                    last_step = trace[-1]
                    # 检查是否是 AI 消息类型
                    return last_step.get("type") == "ai_message"

                # === 任务完成度判断（基于轨迹）===
                is_task_completed = False
                completion_json = {"result": "未知", "reason": "缺少必要信息", "failure_type": "unknown"}
                if agent_error:
                    completion_json = {
                        "result": "未完成",
                        "reason": f"Agent error: {agent_error}",
                        "failure_type": "agent_error",
                    }
                elif action_trace and task_desc:
                    # 检查最后一个步骤是否是 AI 消息，如果不是则判断为 system_error
                    if not _check_last_step_is_ai_message(action_trace):
                        completion_json = {
                            "result": "未完成",
                            "reason": "Agent行为轨迹最后一个步骤不是AI输出的信息",
                            "failure_type": "system_error",
                        }
                        # 如果是system_error且不是最后一次尝试，则重试
                        if attempt < max_retries - 1:
                            log_and_echo(f"[任务 {task_id}] 第 {attempt + 1} 次尝试遇到 system_error，正在重试...")
                            continue
                    else:
                        behavior_text = render_behavior_from_trace(action_trace, max_tool_out_chars=2000)
                        if judge_semaphore:
                            async with judge_semaphore:
                                is_task_completed, _, completion_json = await judge_task_completion(
                                    agent_behavior=behavior_text,
                                    task_description=task_desc,
                                    expected_tools=expected_tools,
                                    judge_model=judge_model,
                                )
                        else:
                            is_task_completed, _, completion_json = await judge_task_completion(
                                agent_behavior=behavior_text,
                                task_description=task_desc,
                                expected_tools=expected_tools,
                                judge_model=judge_model,
                            )
                else:
                    log_and_echo("⚠️  跳过任务完成度判断（缺少必要信息）")

                total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
                mytool_calls = sum(
                    1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in mytool_tool_names
                )

                task_end_time = time.time()
                task_execution_time = task_end_time - task_start_time

                # 如果成功执行到这里，说明任务执行成功，不需要重试
                return _with_defense({
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
                    "action_trace": action_trace,
                }, fides_guard)

            finally:
                if fides_guard is not None:
                    last_defense_summary = fides_guard.summary()
                if limited:
                    try:
                        await limited.close()
                    except Exception as e:
                        log_and_echo(f"⚠️ 关闭 MCP client 失败: {e}")
                if process_id and not keep_isolation:
                    isolation_manager.cleanup_process_isolation_dir(process_id)

        # 如果所有重试都失败了，返回失败结果
        return _with_defense({
            "task_id": task_id,
            "input": user_prompt,
            "expected_tools": expected_tools,
            "agent_final_response": "所有重试都失败了",
            "task_completed": False,
            "completion_reason": {
                "result": "未完成",
                "reason": "所有重试都失败了",
                "failure_type": "system_error",
            },
            "execution_time_seconds": 0,
            "total_tool_calls": 0,
            "mytool_calls": 0,
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
            "action_trace": [],
        })
    # --- 全局配置 ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    RESULTS_DIR = results_dir or f"results/{timestamp}_{model_name}_{dataset_type}"
    os.makedirs(RESULTS_DIR, exist_ok=True)

    RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
    RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")
    TASK_RESULTS_DIR = os.path.join(RESULTS_DIR, "task_results")
    TASK_LOGS_DIR = os.path.join(RESULTS_DIR, "task_logs")
    os.makedirs(TASK_RESULTS_DIR, exist_ok=True)
    os.makedirs(TASK_LOGS_DIR, exist_ok=True)

    setup_run_logger(RUN_LOG_FILE, mode="a" if resume else "w")
    if run_args is not None:
        try:
            log_and_echo("运行参数: " + json.dumps(run_args, ensure_ascii=False, sort_keys=True))
        except TypeError:
            log_and_echo(f"运行参数: {run_args}")
    if run_argv is not None:
        log_and_echo("命令行参数: " + json.dumps(run_argv, ensure_ascii=False))

    all_mcp_config = load_mcp_configs_from_live_config("./configs/live_mcp.json")
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping("./configs/tool2mcp.json")

    # 加载额外的MCP配置（避免重复加载）
    extra_mcp_configs = {}
    extra_mcp_config_path = "./configs/mcp_config.json"
    if os.path.exists(extra_mcp_config_path):
        try:
            with open(extra_mcp_config_path, "r", encoding="utf-8") as f:
                extra_mcp_configs = json.load(f)
        except Exception as e:
            log_and_echo(f"⚠️ 加载额外MCP配置文件失败: {e}")

    # 加载attack数据集（如果提供）
    attack_tool_mapping = {}
    if attack_dataset_path:
        try:
            with open(attack_dataset_path, "r", encoding="utf-8") as f:
                attack_data = json.load(f)
                attack_tool_mapping = {
                    item["task_id"]: item["attack_tools"] for item in attack_data
                }
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
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(
            ".py"
        ):
            tool["args"][0] = os.path.abspath(tool["args"][0])

        if proxy_settings:
            if "env" not in tool:
                tool["env"] = {}
            for key, value in proxy_settings.items():
                if key not in tool["env"]:
                    tool["env"][key] = value

    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://apis.iflow.cn/v1")

    agent_rate_limiter = None
    if agent_rpm_limit and agent_rpm_limit > 0:
        agent_rate_limiter = InMemoryRateLimiter(
            requests_per_second=agent_rpm_limit / 60.0,
            check_every_n_seconds=0.1,
            max_bucket_size=1,
        )

    def create_agent_llm():
        llm_kwargs = {
            "openai_api_key": api_key,
            "openai_api_base": api_base,
            "model": model_name,
            "streaming": False,
            "temperature": 0.0,
            "timeout": 100,
            "max_retries": 1,
        }
        if agent_rate_limiter is not None:
            llm_kwargs["rate_limiter"] = agent_rate_limiter
        return ChatOpenAI(**llm_kwargs)

    concurrency = max(1, int(concurrency or 1))
    judge_concurrency = max(1, int(judge_concurrency or min(concurrency, 3)))
    task_semaphore = asyncio.Semaphore(concurrency)
    judge_semaphore = asyncio.Semaphore(judge_concurrency)
    checkpoint_lock = asyncio.Lock()
    defense = (defense or "none").lower()
    if defense not in {"none", "fides"}:
        log_and_echo(f"⚠️ 未知防御 {defense}，回退为 none")
        defense = "none"
    rpm_msg = f"; agent RPM limit={agent_rpm_limit}" if agent_rate_limiter is not None else ""
    log_and_echo(f"任务并发数: {concurrency}; judge并发数: {judge_concurrency}; resume={resume}{rpm_msg}")
    if defense == "fides":
        log_and_echo(
            "启用 FIDES-style 防御: "
            f"same_tool_same_args_limit={fides_same_tool_same_args_limit}, "
            f"max_total_tool_calls={fides_max_total_tool_calls}, "
            f"label_outputs={fides_label_outputs}, "
            f"block_unsafe_path_writes={fides_block_unsafe_path_writes}"
        )

    results_summary = []

    # 获取 mytool 工具名集合（只需要获取一次）
    mytool_tool_names: set[str] = set()
    mytool_server_key = "mytool"
    mytool_server_path = "./tools/myTool.py"

    # 初始化适应度计算器
    fitness_calculator = None
    if attack:
        # 根据攻击场景类型创建适应度计算器
        try:
            attack_type = AttackType(attack_scenario)
            fitness_calculator = FitnessCalculator(attack_type=attack_type, api_key=api_key)
            log_and_echo(f"初始化适应度计算器: {attack_scenario}")
        except ValueError:
            log_and_echo(f"⚠️ 无效的攻击场景类型: {attack_scenario}，使用默认 resource_waste")
            fitness_calculator = FitnessCalculator(attack_type=AttackType.RESOURCE_WASTE, api_key=api_key)

        mytool_config = {
            "command": "python",
            "args": [os.path.abspath(mytool_server_path)],
            "transport": "stdio",
        }
        # 取第一个任务来获取 mytool 工具名（假设所有任务使用相同的 mytool）
        if dataset:
            first_task = dataset[0]
            first_task_id = first_task["id"]
            if (
                attack_dataset_path
                and first_task_id in attack_tool_mapping
                and attack_tool_mapping[first_task_id]
            ):
                attack_tool = attack_tool_mapping[first_task_id][0]
                config_json = json.dumps(attack_tool, ensure_ascii=False)
                mytool_config["args"].extend([config_json])

            temp_filtered_config = {mytool_server_key: mytool_config}
            if mytool_server_key in temp_filtered_config:
                try:
                    mytool_tool_names = await retry_async(
                        lambda: fetch_server_tool_names(
                            mytool_server_key,
                            temp_filtered_config[mytool_server_key],
                            MultiServerMCPClient,
                        ),
                        tries=3,
                        base=0.6,
                        factor=2.0,
                        max_delay=6.0,
                        name="fetch_server_tool_names",
                    )
                    log_and_echo(f"mytool 工具清单: {sorted(mytool_tool_names)}")
                except Exception as e:
                    log_and_echo(f"⚠️ 获取 mytool 工具名失败，将无法区分其调用：{e}")
                    mytool_tool_names = set()

    # 执行所有任务
    log_and_echo(f"开始执行 {len(dataset)} 个任务")
    if attack and attack_dataset_path:
        log_and_echo(f"启用了攻击模式，将使用攻击数据集: {attack_dataset_path}")

    async def run_one_task(index: int, task: dict):
        task_id = task["id"]
        checkpoint_path = os.path.join(TASK_RESULTS_DIR, _safe_task_filename(index, task_id))
        task_log_path = os.path.join(TASK_LOGS_DIR, _safe_task_filename(index, task_id).replace(".json", ".log"))
        if resume and os.path.exists(checkpoint_path):
            with task_log_context(task_log_path):
                try:
                    with open(checkpoint_path, "r", encoding="utf-8") as f:
                        cached_result = json.load(f)
                    log_and_echo(f"↪ 跳过已完成任务 {index + 1}/{len(dataset)}: {task_id}")
                    return index, cached_result
                except Exception as e:
                    log_and_echo(f"⚠️ 读取checkpoint失败，将重跑任务 {task_id}: {e}")

        async with task_semaphore:
            with task_log_context(task_log_path):
                task_start_msg = f"=============== 并发运行任务 {index + 1}/{len(dataset)}: {task_id} ==============="
                log_and_echo(task_start_msg)
                try:
                    task_result = await _run_task_with_retry(
                        task_id,
                        task["description"],
                        task["input"],
                        task["expected_tools"],
                        attack,
                        attack_dataset_path,
                        attack_tool_mapping,
                        mcp_configs,
                        tool_to_mcp,
                        proxy_settings,
                        extra_mcp_configs,
                        create_agent_llm(),
                        mytool_tool_names,
                        judge_semaphore=judge_semaphore,
                        keep_isolation=keep_isolation,
                        defense=defense,
                        fides_same_tool_same_args_limit=fides_same_tool_same_args_limit,
                        fides_max_total_tool_calls=fides_max_total_tool_calls,
                        fides_label_outputs=fides_label_outputs,
                        fides_block_unsafe_path_writes=fides_block_unsafe_path_writes,
                    )

                    if attack and fitness_calculator and attack_dataset_path:
                        try:
                            attack_tools = attack_tool_mapping.get(task_id, [])
                            if attack_tools:
                                attack_tool = attack_tools[0]
                                async with judge_semaphore:
                                    score, reason = await fitness_calculator.score_async(
                                        task_result,
                                        baseline_ok=True,
                                        attack_tool=attack_tool,
                                    )
                                task_result["attack_score"] = {
                                    "score": score,
                                    "reason": reason,
                                    "attack_scenario": attack_scenario,
                                }
                                log_and_echo(f"任务 {task_id} 攻击评分: {score:.2f} - {reason}")
                            else:
                                log_and_echo(f"任务 {task_id} 没有找到攻击工具，跳过评分")
                        except Exception as e:
                            log_and_echo(f"⚠️ 任务 {task_id} 评分失败: {e}")
                            task_result["attack_score"] = {
                                "score": 0,
                                "reason": f"评分失败: {str(e)}",
                                "attack_scenario": attack_scenario,
                            }
                except Exception as e:
                    log_and_echo(f"❌ 任务 {task_id} 未捕获异常: {e}")
                    task_result = _failed_task_result(task, f"未捕获异常: {e}")

                async with checkpoint_lock:
                    _atomic_write_json(checkpoint_path, task_result)
                return index, task_result

    task_pairs = await asyncio.gather(
        *[run_one_task(index, task) for index, task in enumerate(dataset)],
        return_exceptions=True,
    )
    for index, item in enumerate(task_pairs):
        if isinstance(item, Exception):
            task = dataset[index]
            log_and_echo(f"❌ 任务 {task.get('id')} gather异常: {item}")
            results_summary.append(_failed_task_result(task, f"gather异常: {item}"))
        else:
            _, task_result = item
            results_summary.append(task_result)

    # === 汇总结果 ===
    total_tasks = len(results_summary)
    completed_tasks = sum(1 for r in results_summary if r["task_completed"])
    completion_rate = 0 if total_tasks == 0 else completed_tasks / total_tasks * 100
    overall_total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results_summary)
    overall_mytool_calls = sum(r.get("mytool_calls", 0) for r in results_summary)

    overall_token_usage = {
        "total_tokens": sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results_summary),
        "prompt_tokens": sum(r.get("token_usage", {}).get("prompt_tokens", 0) for r in results_summary),
        "completion_tokens": sum(r.get("token_usage", {}).get("completion_tokens", 0) for r in results_summary),
    }

    # 计算攻击评分统计
    attack_scores = []
    avg_attack_score = 0
    max_attack_score = 0
    min_attack_score = 0
    score_ge_2_count = 0
    score_ge_2_percentage = 0
    score_eq_4_count = 0
    score_eq_4_percentage = 0

    if attack:
        for r in results_summary:
            if "attack_score" in r:
                attack_scores.append(r["attack_score"]["score"])

        if attack_scores:
            avg_attack_score = sum(attack_scores) / len(attack_scores)
            max_attack_score = max(attack_scores)
            min_attack_score = min(attack_scores)

            # 计算大于等于2的数量和百分比
            score_ge_2_count = sum(1 for score in attack_scores if score >= 2)
            score_ge_2_percentage = (score_ge_2_count / len(attack_scores)) * 100 if attack_scores else 0

            # 计算等于4的数量和百分比
            score_eq_4_count = sum(1 for score in attack_scores if score == 4)
            score_eq_4_percentage = (score_eq_4_count / len(attack_scores)) * 100 if attack_scores else 0

            attack_score_stats = {
                "average_score": avg_attack_score,
                "max_score": max_attack_score,
                "min_score": min_attack_score,
                "scenario": attack_scenario,
                "score_ge_2": {
                    "count": score_ge_2_count,
                    "percentage": score_ge_2_percentage
                },
                "score_eq_4": {
                    "count": score_eq_4_count,
                    "percentage": score_eq_4_percentage
                }
            }
        else:
            attack_score_stats = {
                "average_score": 0,
                "max_score": 0,
                "min_score": 0,
                "scenario": attack_scenario,
                "score_ge_2": {
                    "count": 0,
                    "percentage": 0
                },
                "score_eq_4": {
                    "count": 0,
                    "percentage": 0
                }
            }

    final_report = {
        "run_timestamp": datetime.now().isoformat(),
        "overall_statistics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": f"{completion_rate:.2f}%",
            "total_tool_calls": overall_total_tool_calls,
            "mytool_calls": overall_mytool_calls,
            "token_usage": overall_token_usage,
            "attack_scenario": attack_scenario if attack else None,
            "attack_score_statistics": attack_score_stats if attack else None,
            "defense": {
                "name": defense,
                "fides_same_tool_same_args_limit": fides_same_tool_same_args_limit if defense == "fides" else None,
                "fides_max_total_tool_calls": fides_max_total_tool_calls if defense == "fides" else None,
                "fides_label_outputs": fides_label_outputs if defense == "fides" else None,
                "fides_block_unsafe_path_writes": fides_block_unsafe_path_writes if defense == "fides" else None,
            },
        },
        "task_details": results_summary,
    }

    with open(RESULT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print("\n================= 所有任务运行完毕 =================\n")
    print(f"📊 任务完成率: {completion_rate:.2f}% ({completed_tasks}/{total_tasks})")
    print(f"📊 总工具调用次数: {overall_total_tool_calls}，其中 mytool: {overall_mytool_calls}")
    print(
        f"📊 总token使用量: {overall_token_usage['total_tokens']} "
        f"(提示: {overall_token_usage['prompt_tokens']}, 完成: {overall_token_usage['completion_tokens']})"
    )

    # 显示攻击评分统计
    if attack and attack_scores:
        print(f"🎯 攻击场景: {attack_scenario}")
        print(f"🎯 攻击评分统计 - 平均分: {avg_attack_score:.2f}, 最高分: {max_attack_score:.2f}, 最低分: {min_attack_score:.2f}")
        if attack_scores:
            print(f"📈 评分≥2: {score_ge_2_count}个 ({score_ge_2_percentage:.1f}%)")
            print(f"⭐ 评分=4: {score_eq_4_count}个 ({score_eq_4_percentage:.1f}%)")

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
        ),
    )
    parser.add_argument("--use-mytool", action="store_true", help="启用 mytool MCP server")
    parser.add_argument("--attack-dataset", type=str, help="attack数据集路径")
    parser.add_argument("--attack-scenario", type=str, choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"], default="resource_waste", help="攻击场景类型 (默认: resource_waste)")
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

        asyncio.run(
            main(
                dataset,
                attack=args.use_mytool,
                attack_dataset_path=args.attack_dataset,
                attack_scenario=args.attack_scenario,
                run_args=vars(args),
                run_argv=sys.argv,
            )
        )
    else:
        print("错误: 没有找到任何有效的数据集文件")
