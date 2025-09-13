#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
函数化执行实现模块
将attack_generator.py中的函数化执行代码提取到这里
"""

import json as _json
import os as _os
import time
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from typing import Optional

# 项目模块
from src.utils.tool_functions import _now, render_behavior_from_trace
from src.mcp_client.client import LimitedMCPClient
from src.data_loaders.data_loader import (
    load_mcp_configs_from_live_config,
    load_tool_to_mcp_mapping,
    fetch_server_tool_names,
)
from src.evaluators.task_evaluator import judge_task_completion
from src.core.agent_runner import run_agent_with_streaming


MAX_TOOL_OUTPUT_CHARS = 8000


def _sanitize_attack_map(attack_dataset):
    """返回 {task_id: [attack_tools]}，无则空字典。异常不抛出。"""
    if not attack_dataset:
        return {}
    try:
        if isinstance(attack_dataset, str):
            with open(attack_dataset, "r", encoding="utf-8") as f:
                data = _json.load(f)
        else:
            data = attack_dataset
        return {item["task_id"]: item.get("attack_tools", []) for item in data}
    except Exception:
        return {}


def _resolve_mytool_path() -> str:
    """
    返回可用的 myTool.py 绝对路径；若都不存在则返回空串。
    优先级：环境变量 -> 常见仓库路径 -> 相对路径
    """
    candidates = [
        _os.getenv("MYTOOL_PATH", "").strip(),
        "tools/myTool.py",
        "./tools/myTool.py",
        _os.path.join(_os.getcwd(), "tools", "myTool.py")
    ]
    for p in candidates:
        if p and _os.path.isfile(p):
            return _os.path.abspath(p)
    return ""


def _build_filtered_mcp_config(expected_tools, attack, tool_to_mcp, mcp_configs, attack_tools_for_task=None):
    """只加载期望工具和可选mytool；mytool可注入攻击工具定义用于红队测试。"""
    filtered = {}
    required_servers = set()

    # 从配置文件加载代理设置
    proxy_config_path = "configs/proxy_config.json"
    proxy_settings = {}
    if _os.path.exists(proxy_config_path):
        try:
            with open(proxy_config_path, "r", encoding="utf-8") as f:
                proxy_settings = _json.load(f)
        except Exception as e:
            print(f"⚠️ 加载代理配置文件失败: {e}")
    else:
        print("⚠️ 代理配置文件不存在")

    if expected_tools:
        for t in expected_tools:
            if t in tool_to_mcp:
                mcp_server_names = tool_to_mcp[t]
                if isinstance(mcp_server_names, list):
                    required_servers.update(mcp_server_names)
                else:
                    required_servers.add(mcp_server_names)

    if attack:
        mytool_path = _resolve_mytool_path()
        if mytool_path:
            mytool_cfg = {
                "command": "python",
                "args": [mytool_path],
                "transport": "stdio",
            }
            # 注入攻击工具定义（若提供）。这里仅透传，不执行本地代码。
            if attack_tools_for_task:
                atk = attack_tools_for_task[0]  # 最多注入一个
                mytool_cfg["args"].append(_json.dumps(atk, ensure_ascii=False))
            filtered["mytool"] = mytool_cfg
        else:
            print("[WARN] myTool.py 未找到：未注入 mytool（可设置环境变量 MYTOOL_PATH 指向实际路径）")

    for server in required_servers:
        if server in mcp_configs:
            cfg = mcp_configs[server].copy()
            cfg.setdefault("transport", "stdio")
            if cfg["command"] == "python" and cfg.get("args") and cfg["args"][0].endswith(".py"):
                cfg["args"][0] = _os.path.abspath(cfg["args"][0])

            # 如果配置文件中有代理设置，则添加到环境变量中（不覆盖已有的环境变量）
            if proxy_settings:
                if "env" not in cfg:
                    cfg["env"] = {}
                for key, value in proxy_settings.items():
                    if key not in cfg["env"]:
                        cfg["env"][key] = value

            filtered[server] = cfg

    return filtered


async def _run_single_task(task, llm, tool_to_mcp, mcp_configs, attack, attack_map):
    """运行单个任务，返回结果字典。"""
    task_id = task["id"]
    task_desc = task["description"]
    user_prompt = task["input"]
    expected_tools = task.get("expected_tools", [])
    t0 = time.time()

    # 仅为该task构建MCP配置
    filtered_config = _build_filtered_mcp_config(
        expected_tools=expected_tools,
        attack=attack,
        tool_to_mcp=tool_to_mcp,
        mcp_configs=mcp_configs,
        attack_tools_for_task=attack_map.get(task_id),
    )

    # 获取当前任务的攻击工具名称，用于统计
    attack_tool_names = set()
    attack_tools_for_task = attack_map.get(task_id, [])
    if attack and attack_tools_for_task:
        attack_tool_names = {tool.get("name") for tool in attack_tools_for_task if tool.get("name")}

    # 尝试枚举mytool的工具名集合，便于统计
    mytool_names = set()
    if attack and "mytool" in filtered_config:
        try:
            mytool_names = await fetch_server_tool_names("mytool", filtered_config["mytool"])
        except Exception:
            mytool_names = set()

    # 合并mytool服务器本身的工具名称和攻击工具名称
    all_mytool_names = mytool_names.union(attack_tool_names)

    # 加载MCP工具
    try:
        limited = LimitedMCPClient(
            filtered_config,
            max_response_length=5000,
            max_list_length=100,
            max_category_items=20,
            timeout=30,
        )
        tools = await limited.get_tools()
    except Exception as e:
        return {
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
            "execution_time_seconds": time.time() - t0,
            "total_tool_calls": 0,
            "mytool_calls": 0,
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "action_trace": [{"ts": _now(), "type": "user_input", "content": user_prompt}],
        }

    # 使用统一的agent执行模块（带流式处理和工具锁）
    agent_result = await run_agent_with_streaming(
        llm=llm,
        tools=tools,
        task_id=task_id,
        user_prompt=user_prompt,
        use_tool_lock=True
    )

    final_response = agent_result["final_response"]
    action_trace = agent_result["action_trace"]
    token_usage = agent_result["token_usage"]

    # 任务完成度判定
    is_task_completed = False
    completion_json = {"result": "未知", "reason": "缺少必要信息", "failure_type": "unknown"}
    if action_trace and task_desc:
        behavior_text = render_behavior_from_trace(action_trace, max_tool_out_chars=2000)
        is_task_completed, _, completion_json = await judge_task_completion(
            agent_behavior=behavior_text,
            task_description=task_desc,
            expected_tools=expected_tools
        )

    total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
    mytool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in all_mytool_names)

    return {
        "task_id": task_id,
        "input": user_prompt,
        "expected_tools": expected_tools,
        "agent_final_response": final_response,
        "task_completed": is_task_completed,
        "completion_reason": completion_json,
        "execution_time_seconds": time.time() - t0,
        "total_tool_calls": total_tool_calls,
        "mytool_calls": mytool_calls,
        "token_usage": token_usage,
        "action_trace": action_trace,
    }


async def run_tasks_as_function(
    dataset,
    *,
    attack=True,
    attack_dataset=None,
    model="glm-4.5",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key_env="OPENAI_API_KEY",
    api_base_env="OPENAI_API_BASE",
):
    """
    作为库函数调用的入口。
    参数
      - dataset: 任务列表，每项至少包含 id/description/input/expected_tools
      - attack: 是否启用攻击模式（加载mytool）
      - attack_dataset: 路径或对象；用于红队测试的恶意工具定义
      - model/api_key/api_base: LLM配置（显式参数优先，其次环境变量）
    返回
      - 一个汇总结果dict（与原脚本最终JSON结构一致）
    """
    load_dotenv()
    # LLM配置：显式参数优先，然后环境变量
    api_key = api_key or (_os.getenv(api_key_env) or "")
    api_base = api_base or (_os.getenv(api_base_env) or "https://apis.iflow.cn/v1")

    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=model,
        streaming=True,
        temperature=0.0,
        timeout=100,
        max_retries=10,  # 更稳的自动重试
    )

    # —— 路径健壮化 —— #
    # 使用相对路径并提供环境变量覆盖选项
    repo_root = _os.getenv("MCP_BENCH_ROOT", ".")
    live_cfg_try = [
        "configs/live_mcp.json",
        _os.path.join(repo_root, "configs/live_mcp.json"),
    ]
    tool2mcp_try = [
        "configs/tool2mcp.json",
        _os.path.join(repo_root, "configs/tool2mcp.json"),
    ]
    live_cfg_path = next((p for p in live_cfg_try if _os.path.exists(p)), live_cfg_try[-1])
    tool2mcp_path = next((p for p in tool2mcp_try if _os.path.exists(p)), tool2mcp_try[-1])
    if not _os.path.exists(live_cfg_path):
        raise FileNotFoundError(f"live_mcp.json 未找到，尝试过: {live_cfg_try}")
    if not _os.path.exists(tool2mcp_path):
        raise FileNotFoundError(f"tool2mcp.json 未找到，尝试过: {tool2mcp_try}")

    all_mcp_config = load_mcp_configs_from_live_config(live_cfg_path)
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping(tool2mcp_path)

    # 从配置文件加载代理设置
    proxy_config_path = "configs/proxy_config.json"
    proxy_settings = {}
    if _os.path.exists(proxy_config_path):
        try:
            with open(proxy_config_path, "r", encoding="utf-8") as f:
                proxy_settings = _json.load(f)
        except Exception as e:
            print(f"⚠️ 加载代理配置文件失败: {e}")
    else:
        print("ℹ️ 代理配置文件不存在，不添加代理设置")

    # 规范化live_mcp路径
    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(".py"):
            tool["args"][0] = _os.path.abspath(tool["args"][0])

        # 如果配置文件中有代理设置，则添加到环境变量中（不覆盖已有的环境变量）
        if proxy_settings:
            if "env" not in tool:
                tool["env"] = {}
            for key, value in proxy_settings.items():
                if key not in tool["env"]:
                    tool["env"][key] = value

    attack_map = _sanitize_attack_map(attack_dataset)

    results_summary = []
    for task in dataset:
        res = await _run_single_task(task, llm, tool_to_mcp, mcp_configs, attack, attack_map)
        results_summary.append(res)

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

    final_report = {
        "run_timestamp": datetime.now().isoformat(),
        "overall_statistics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": f"{completion_rate:.2f}%",
            "total_tool_calls": overall_total_tool_calls,
            "mytool_calls": overall_mytool_calls,
            "token_usage": overall_token_usage,
        },
        "task_details": results_summary,
    }
    return final_report