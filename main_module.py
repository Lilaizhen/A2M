import asyncio
import json
import os
import time
import re
from datetime import datetime
import argparse
from random import random

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback

# Load project modules
from src.utils.logging_config import setup_run_logger, log_and_echo
from src.utils.tool_functions import truncate_tool_outputs, _now, _as_text, render_behavior_from_trace
from src.mcp_client.client import LimitedMCPClient
from src.agents.agent_utils import format_agent_step
from src.evaluators.task_evaluator import judge_task_completion
from src.data_loaders.data_loader import (
    load_mcp_configs_from_live_config,
    load_tool_to_mcp_mapping,
    fetch_server_tool_names,
    load_dataset,
)
from src.core.executor import TaskExecutor
import shutil
from src.attacks.scoring.fitness_calculator import FitnessCalculator, AttackType

load_dotenv()  # Load env vars from .env


def _convert_relative_paths_in_text(text):
    """
    Find relative paths like "./path/to/file" in text and convert them to absolute paths.
    Only converts paths starting with ./ or ../.
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


def _reset_annotated_data():
    """
    Reset the annotated_data folder to the backup state.
    """
    annotated_data_path = "./annotated_data"
    annotated_data_backup_path = "./annotated_data_backup"

    if os.path.exists(annotated_data_path):
        shutil.rmtree(annotated_data_path)

    if os.path.exists(annotated_data_backup_path):
        shutil.copytree(annotated_data_backup_path, annotated_data_path)
    else:
        os.makedirs(annotated_data_path, exist_ok=True)


# --- Global config ---
RESULTS_DIR = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
os.makedirs(RESULTS_DIR, exist_ok=True)

RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")

# Optional: limit single tool output characters written to trace
MAX_TOOL_OUTPUT_CHARS = 8000


# ============ Retry helpers ============
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
    Exponential backoff + jitter retry for async operations.
    op: zero-arg callable returning a coroutine.
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
                f"↻ Retry {name} ({i+1}/{tries-1}) due to {e.__class__.__name__}: {str(e)[:120]} ; wait {delay:.2f}s"
            )
            await asyncio.sleep(delay)
    raise last
# ============================================


async def main(
    dataset,
    attack: bool = True,
    attack_dataset_path: str = None,
    attack_scenario: str = "resource_waste",
    model_name: str = None,
    judge_model: str = None,
    dataset_type: str = "all",
):
    # Retry wrapper for running a single task
    async def _run_task_with_retry(
        task_id, task_desc, user_prompt, expected_tools, attack, attack_dataset_path,
        attack_tool_mapping, mcp_configs, tool_to_mcp, proxy_settings, extra_mcp_configs,
        llm, mytool_tool_names
    ):
        max_retries = 5
        for attempt in range(max_retries):
            task_start_time = time.time()
            if attempt > 0:
                log_and_echo(f"=============== Retrying task {task_id} ({task_desc}) [attempt {attempt + 1}/{max_retries}] ===============")

            # === Use annotated_data directory ===
            temp_dir = "./annotated_data"
            if attempt == 0:
                log_and_echo(f"🔧 Using annotated_data directory: {temp_dir}")

            _reset_annotated_data()
            if attempt == 0:
                log_and_echo("🔄 Reset annotated_data directory to backup state")

            try:
                # === Build filtered_config (expected tools + optional mytool + extra configs) ===
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

                # Add extra MCP configs (avoid duplicate loads)
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

                if attempt == 0:
                    log_and_echo("🧪 Tools to load: " + str(list(filtered_config.keys())))

                # === Dynamically fetch mytool tool names (with retry) ===
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
                        log_and_echo(f"mytool tool list: {sorted(mytool_tool_names_inner)}")
                    except Exception as e:
                        log_and_echo(f"⚠️ Failed to fetch mytool tool names; will not distinguish its calls: {e}")
                        mytool_tool_names_inner = set()

                # --- Load MCP tools (LimitedMCPClient with retry) ---
                try:
                    limited = LimitedMCPClient(
                        filtered_config,
                        max_response_length=5000,
                        max_list_length=100,
                        max_category_items=20,
                        timeout=30,
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
                    log_and_echo(f"❌ Failed to load MCP tools: {e}")
                    if attempt < max_retries - 1:
                        log_and_echo(f"[Task {task_id}] Attempt {attempt + 1} hit MCP tool load failure, retrying...")
                        continue
                    else:
                        task_end_time = time.time()
                        task_execution_time = task_end_time - task_start_time

                        return {
                            "task_id": task_id,
                            "input": user_prompt,
                            "expected_tools": expected_tools,
                            "agent_final_response": "MCP tool loading failed",
                            "task_completed": False,
                            "completion_reason": {
                                "result": "incomplete",
                                "reason": f"MCP tool loading failed: {e.__class__.__name__}",
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
                        }

                # --- Create Agent and run (fault tolerant) ---
                final_response = ""
                action_trace = []  # action trace
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

                                # 1) Tool output
                                if isinstance(last_message, ToolMessage):
                                    tool_output_text = _as_text(last_message.content)
                                    if (
                                        isinstance(tool_output_text, str)
                                        and len(tool_output_text) > MAX_TOOL_OUTPUT_CHARS
                                    ):
                                        tool_output_text = (
                                            tool_output_text[:MAX_TOOL_OUTPUT_CHARS]
                                            + "...(truncated)"
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

                                # 2) AI messages + tool calls
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
                                            log_and_echo(tc_prety if (tc_prety := tc_pretty) else tc_pretty)  # Keep local var reference compatibility
                                            current_tool_execution = name
                                    continue

                                # 3) Fallback: dict-style tool_call
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
                                log_and_echo("Agent streaming execution timed out (>500s)")
                                action_trace.append(
                                    {
                                        "ts": _now(),
                                        "type": "ai_message",
                                        "content": "Agent execution timed out (>500s)",
                                    }
                                )

                        # Add another retry layer for streaming to resist transient issues
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
                    log_and_echo(f"❌ Agent execution failed: {e}")
                    if attempt < max_retries - 1:
                        log_and_echo(f"[Task {task_id}] Attempt {attempt + 1} hit agent failure, retrying...")
                        continue
                    else:
                        task_end_time = time.time()
                        task_execution_time = task_end_time - task_start_time
                        return {
                            "task_id": task_id,
                            "input": user_prompt,
                            "expected_tools": expected_tools,
                            "agent_final_response": f"Agent execution failed: {e}",
                            "task_completed": False,
                            "completion_reason": {
                                "result": "incomplete",
                                "reason": f"Agent execution failed: {e.__class__.__name__}",
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
                        }

                def _check_last_step_is_ai_message(trace):
                    """Check whether the last step in the trace is an AI message."""
                    if not trace:
                        return False
                    # Get last step
                    last_step = trace[-1]
                    # Verify it is an AI message
                    return last_step.get("type") == "ai_message"

                is_task_completed = False
                completion_json = {"result": "unknown", "reason": "Missing required info", "failure_type": "unknown"}
                if agent_error:
                    completion_json = {
                        "result": "incomplete",
                        "reason": f"Agent error: {agent_error}",
                        "failure_type": "agent_error",
                    }
                elif action_trace and task_desc:
                    if not _check_last_step_is_ai_message(action_trace):
                        completion_json = {
                            "result": "incomplete",
                            "reason": "Last step in agent trace is not an AI message",
                            "failure_type": "system_error",
                        }
                        if attempt < max_retries - 1:
                            log_and_echo(f"[Task {task_id}] Attempt {attempt + 1} hit system_error, retrying...")
                            continue
                    else:
                        behavior_text = render_behavior_from_trace(action_trace, max_tool_out_chars=2000)
                        is_task_completed, _, completion_json = await judge_task_completion(
                            agent_behavior=behavior_text,
                            task_description=task_desc,
                            expected_tools=expected_tools,
                            judge_model=judge_model,
                        )
                else:
                    log_and_echo("⚠️  Skip completion judgment (missing necessary info)")

                total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
                mytool_calls = sum(
                    1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in mytool_tool_names
                )

                task_end_time = time.time()
                task_execution_time = task_end_time - task_start_time

                return {
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
                }

            finally:
                if attempt == 0:
                    log_and_echo(f"ℹ️  Using annotated_data directory; no cleanup needed")

        return {
            "task_id": task_id,
            "input": user_prompt,
            "expected_tools": expected_tools,
            "agent_final_response": "All retries failed",
            "task_completed": False,
            "completion_reason": {
                "result": "incomplete",
                "reason": "All retries failed",
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
        }
    # --- Global config for run ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    RESULTS_DIR = f"results/{timestamp}_{model_name}_{dataset_type}"
    os.makedirs(RESULTS_DIR, exist_ok=True)

    RUN_LOG_FILE = os.path.join(RESULTS_DIR, "run.log")
    RESULT_JSON_FILE = os.path.join(RESULTS_DIR, "results.json")

    setup_run_logger(RUN_LOG_FILE)

    all_mcp_config = load_mcp_configs_from_live_config("./configs/live_mcp.json")
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping("./configs/tool2mcp.json")

    # Load extra MCP configs (to avoid reloading)
    extra_mcp_configs = {}
    extra_mcp_config_path = "./configs/mcp_config.json"
    if os.path.exists(extra_mcp_config_path):
        try:
            with open(extra_mcp_config_path, "r", encoding="utf-8") as f:
                extra_mcp_configs = json.load(f)
        except Exception as e:
            log_and_echo(f"⚠️ Failed to load extra MCP config: {e}")

    # Load attack dataset (if provided)
    attack_tool_mapping = {}
    if attack_dataset_path:
        try:
            with open(attack_dataset_path, "r", encoding="utf-8") as f:
                attack_data = json.load(f)
                attack_tool_mapping = {
                    item["task_id"]: item["attack_tools"] for item in attack_data
                }
        except Exception as e:
            log_and_echo(f"⚠️ Failed to load attack dataset: {e}")

    # Load proxy settings
    proxy_config_path = "./configs/proxy_config.json"
    proxy_settings = {}
    if os.path.exists(proxy_config_path):
        try:
            with open(proxy_config_path, "r", encoding="utf-8") as f:
                proxy_settings = json.load(f)
        except Exception as e:
            log_and_echo(f"⚠️ Failed to load proxy config: {e}")
    else:
        log_and_echo("ℹ️ Proxy config file missing; no proxy settings added")

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
    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=model_name,
        streaming=False,
        temperature=0.0,
        timeout=100,  # Business LLM 100s
        max_retries=1,
    )

    results_summary = []

    # Fetch mytool tool names once
    mytool_tool_names: set[str] = set()
    mytool_server_key = "mytool"
    mytool_server_path = "./tools/myTool.py"

    # Initialize fitness calculator
    fitness_calculator = None
    if attack:
        # Build fitness calculator for the attack scenario
        try:
            attack_type = AttackType(attack_scenario)
            fitness_calculator = FitnessCalculator(attack_type=attack_type, api_key=api_key)
            log_and_echo(f"Initialized fitness calculator: {attack_scenario}")
        except ValueError:
            log_and_echo(f"⚠️ Invalid attack scenario type: {attack_scenario}, using default resource_waste")
            fitness_calculator = FitnessCalculator(attack_type=AttackType.RESOURCE_WASTE, api_key=api_key)

        mytool_config = {
            "command": "python",
            "args": [os.path.abspath(mytool_server_path)],
            "transport": "stdio",
        }
        # Use first task to fetch mytool tool names (assumes same across tasks)
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
                    log_and_echo(f"mytool tool list: {sorted(mytool_tool_names)}")
                except Exception as e:
                    log_and_echo(f"⚠️ Failed to fetch mytool tool names; will not distinguish its calls: {e}")
                    mytool_tool_names = set()

    # Execute tasks
    log_and_echo(f"Starting {len(dataset)} tasks")
    if attack and attack_dataset_path:
        log_and_echo(f"Attack mode enabled; using attack dataset: {attack_dataset_path}")

    for task in dataset:
        task_id = task["id"]
        task_desc = task["description"]
        user_prompt = task["input"]
        expected_tools = task["expected_tools"]

        # Execute task with retry wrapper
        task_result = await _run_task_with_retry(
            task_id, task_desc, user_prompt, expected_tools, attack, attack_dataset_path,
            attack_tool_mapping, mcp_configs, tool_to_mcp, proxy_settings, extra_mcp_configs,
            llm, mytool_tool_names
        )

        # If attack mode is on, compute fitness score
        if attack and fitness_calculator and attack_dataset_path:
            try:
                # Fetch attack tools for current task
                attack_tools = attack_tool_mapping.get(task_id, [])
                if attack_tools:
                    # Use the first attack tool for scoring
                    attack_tool = attack_tools[0]
                    # Compute score
                    score, reason = await fitness_calculator.score_async(task_result, baseline_ok=True, attack_tool=attack_tool)

                    # Attach score to task result
                    task_result["attack_score"] = {
                        "score": score,
                        "reason": reason,
                        "attack_scenario": attack_scenario
                    }

                    log_and_echo(f"Task {task_id} attack score: {score:.2f} - {reason}")
                else:
                    log_and_echo(f"Task {task_id} has no attack tool; skip scoring")
            except Exception as e:
                log_and_echo(f"⚠️ Task {task_id} scoring failed: {e}")
                task_result["attack_score"] = {
                    "score": 0,
                    "reason": f"Scoring failed: {str(e)}",
                    "attack_scenario": attack_scenario
                }

        results_summary.append(task_result)

    # === Summaries ===
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

    # Attack score stats
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

            # Count scores >= 2 and percentage
            score_ge_2_count = sum(1 for score in attack_scores if score >= 2)
            score_ge_2_percentage = (score_ge_2_count / len(attack_scores)) * 100 if attack_scores else 0

            # Count scores = 4 and percentage
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
        },
        "task_details": results_summary,
    }

    with open(RESULT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4, ensure_ascii=False)

    print("\n================= All tasks finished =================\n")
    print(f"📊 Completion rate: {completion_rate:.2f}% ({completed_tasks}/{total_tasks})")
    print(f"📊 Total tool calls: {overall_total_tool_calls}, mytool: {overall_mytool_calls}")
    print(
        f"📊 Total token usage: {overall_token_usage['total_tokens']} "
        f"(prompt: {overall_token_usage['prompt_tokens']}, completion: {overall_token_usage['completion_tokens']})"
    )

    # Show attack score stats
    if attack and attack_scores:
        print(f"🎯 Attack scenario: {attack_scenario}")
        print(f"🎯 Attack score stats - Avg: {avg_attack_score:.2f}, Max: {max_attack_score:.2f}, Min: {min_attack_score:.2f}")
        if attack_scores:
            print(f"📈 Scores ≥2: {score_ge_2_count} ({score_ge_2_percentage:.1f}%)")
            print(f"⭐ Scores =4: {score_eq_4_count} ({score_eq_4_percentage:.1f}%)")

    print(f"📄 Results JSON path: {RESULT_JSON_FILE}")
    print(f"📝 Run log path: {RUN_LOG_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Choose dataset: all, test, filter
    parser.add_argument(
        "--dataset",
        choices=["all", "test", "filter"],
        default="all",
        help=(
            "Choose dataset:\n"
            "all=./datasets/all_annotations.json (default)\n"
            "test=./datasets/test_prompts.json\n"
            "filter=./datasets/all_annotations_filter.json"
        ),
    )
    parser.add_argument("--use-mytool", action="store_true", help="Enable mytool MCP server")
    parser.add_argument("--attack-dataset", type=str, help="Path to attack dataset")
    parser.add_argument("--attack-scenario", type=str, choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"], default="resource_waste", help="Attack scenario type (default: resource_waste)")
    args = parser.parse_args()

    # Dataset path mapping
    if args.dataset == "test":
        data_path = "./datasets/test_prompts.json"
    elif args.dataset == "filter":
        data_path = "./datasets/all_annotations_filter.json"
    else:  # default all
        data_path = "./datasets/all_annotations.json"

    dataset = load_dataset(data_path)

    # Ensure relative paths in tasks are converted to absolute paths
    if dataset:
        for task in dataset:
            if "description" in task:
                task["description"] = _convert_relative_paths_in_text(task["description"])
            if "input" in task:
                task["input"] = _convert_relative_paths_in_text(task["input"])

        asyncio.run(main(dataset, attack=args.use_mytool, attack_dataset_path=args.attack_dataset, attack_scenario=args.attack_scenario))
    else:
        print("Error: no valid dataset files found")
