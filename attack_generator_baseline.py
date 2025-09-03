#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP-Bench 基线评测器（无攻击场景）
- 跑一遍所有任务（不注入 mytool）
- 记录总体统计与每个任务的执行详情到输出 JSON
- 路径健壮化：支持 CLI > 环境变量 > 常见默认路径
"""

import argparse
import json
import os
import sys
from typing import Dict, List

# ========== ▼▼▼ 引入“函数化执行”实现（原样整块合并） ▼▼▼ ==========

# -*- coding: utf-8 -*-
import asyncio, json as _json, os as _os, time
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback

# 你项目里的模块
from src.utils.tool_functions import _now, _as_text, render_behavior_from_trace
from src.mcp_client.client import LimitedMCPClient
from src.evaluators.task_evaluator import judge_task_completion
from src.data_loaders.data_loader import (
    load_mcp_configs_from_live_config,
    load_tool_to_mcp_mapping,
    fetch_server_tool_names,
)

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

def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return os.path.abspath(p)
    return None

def _resolve_paths(args):
    """
    统一解析：
      - repo_root（仓库根）
      - live_mcp.json
      - tool2mcp.json
    优先级：命令行参数 > 环境变量 > 常见默认路径 > CWD 猜测
    """
    repo_root = (
        args.repo_root
        or os.getenv("MCP_BENCH_ROOT")
        or "/home/llz/MCP-Bench"
    )
    repo_root = os.path.abspath(repo_root)

    live_arg = args.live_config or os.getenv("LIVE_MCP_PATH")
    tool2_arg = args.tool2mcp or os.getenv("TOOL2MCP_PATH")

    live_candidates = [
        live_arg,
        os.path.join(repo_root, "configs/live_mcp.json"),
        "./configs/live_mcp.json",
        os.path.join(os.getcwd(), "configs", "live_mcp.json"),
    ]
    tool2_candidates = [
        tool2_arg,
        os.path.join(repo_root, "configs/tool2mcp.json"),
        "./configs/tool2mcp.json",
        os.path.join(os.getcwd(), "configs", "tool2mcp.json"),
    ]

    live_cfg_path = _first_existing(live_candidates)
    tool2mcp_path = _first_existing(tool2_candidates)

    print("[PATH] repo_root     =", repo_root)
    print("[PATH] live_mcp.json =", live_cfg_path or "NOT FOUND")
    print("[PATH] tool2mcp.json =", tool2mcp_path or "NOT FOUND")

    if not live_cfg_path:
        raise FileNotFoundError(f"live_mcp.json 未找到，尝试过: {live_candidates}")
    if not tool2mcp_path:
        raise FileNotFoundError(f"tool2mcp.json 未找到，尝试过: {tool2_candidates}")

    return {
        "repo_root": repo_root,
        "live_cfg_path": live_cfg_path,
        "tool2mcp_path": tool2mcp_path,
    }

def _build_filtered_mcp_config(expected_tools, attack, tool_to_mcp, mcp_configs, attack_tools_for_task=None):
    """只加载期望工具；本脚本跑“无攻击基线”，即 attack=False 时不注入 mytool。"""
    filtered = {}
    required_servers = set()
    if expected_tools:
        for t in expected_tools:
            if t in tool_to_mcp:
                required_servers.add(tool_to_mcp[t])

    for server in required_servers:
        if server in mcp_configs:
            cfg = mcp_configs[server].copy()
            cfg.setdefault("transport", "stdio")
            if cfg["command"] == "python" and cfg.get("args") and cfg["args"][0].endswith(".py"):
                cfg["args"][0] = os.path.abspath(cfg["args"][0])
            filtered[server] = cfg

    return filtered

async def _run_single_task(task, llm, tool_to_mcp, mcp_configs, attack, attack_map):
    """运行单个任务，返回结果字典。"""
    task_id = task["id"]
    task_desc = task["description"]
    user_prompt = task["input"]
    expected_tools = task.get("expected_tools", [])
    t0 = time.time()

    filtered_config = _build_filtered_mcp_config(
        expected_tools=expected_tools,
        attack=attack,
        tool_to_mcp=tool_to_mcp,
        mcp_configs=mcp_configs,
        attack_tools_for_task=None,  # 基线：不注入攻击工具
    )

    # 无攻击时，这里始终为空集合
    mytool_names = set()

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

    final_response = ""
    action_trace = [{"ts": _now(), "type": "user_input", "content": user_prompt}]
    token_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

    agent = create_react_agent(llm, tools, checkpointer=MemorySaver())
    config = {"recursion_limit": 100, "configurable": {"thread_id": f"task-{task_id}"}}
    user_msg = {"messages": [{"role": "user", "content": user_prompt}]}

    async def _drain():
        nonlocal final_response
        async for step in agent.astream(user_msg, config, stream_mode="values"):
            last = step["messages"][-1]
            if isinstance(last, ToolMessage):
                out = _as_text(last.content)
                if isinstance(out, str) and len(out) > MAX_TOOL_OUTPUT_CHARS:
                    out = out[:MAX_TOOL_OUTPUT_CHARS] + "...(截断)"
                action_trace.append({"ts": _now(), "type": "tool_output", "tool": last.name, "output": out})
            elif isinstance(last, AIMessage):
                txt = _as_text(last.content).strip()
                if txt:
                    final_response = txt
                    action_trace.append({"ts": _now(), "type": "ai_message", "content": txt})
                tool_calls = getattr(last, "tool_calls", None) or last.additional_kwargs.get("tool_calls", [])
                if tool_calls:
                    tc = tool_calls[0]
                    fn = (tc.get("function") or {})
                    name = fn.get("name") or tc.get("name", "unknown_tool")
                    args = fn.get("arguments") or tc.get("args") or {}
                    try:
                        if isinstance(args, str):
                            args = _json.loads(args)
                    except Exception:
                        pass
                    action_trace.append({"ts": _now(), "type": "tool_call", "tool": name, "args": args})

    try:
        with get_openai_callback() as cb:
            await asyncio.wait_for(_drain(), timeout=500)
            token_usage = {
                "total_tokens": cb.total_tokens,
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
            }
    except asyncio.TimeoutError:
        action_trace.append({"ts": _now(), "type": "ai_message", "content": "Agent 执行超时（>500s）"})

    is_task_completed = False
    completion_json = {"result": "未知", "reason": "缺少必要信息", "failure_type": "unknown"}
    if action_trace and task_desc:
        behavior_text = render_behavior_from_trace(action_trace, max_tool_out_chars=2000)
        is_task_completed, _, completion_json = await judge_task_completion(
            agent_behavior=behavior_text,
            task_description=task_desc,
            expected_tools=expected_tools,
        )

    total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
    mytool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in mytool_names)

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
    attack=False,                 # 基线：默认 False
    attack_dataset=None,          # 基线：忽略
    model="glm-4.5",
    api_key_env="OPENAI_API_KEY",
    api_base_env="OPENAI_API_BASE",
    live_cfg_path: str = None,    # 由 main() 解析传入
    tool2mcp_path: str = None,    # 由 main() 解析传入
):
    """
    作为库函数调用的入口（基线评测）。
    """
    load_dotenv()

    api_key = os.getenv(api_key_env) or ""
    api_base = os.getenv(api_base_env) or "https://apis.iflow.cn/v1"

    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=model,
        streaming=True,
        temperature=0.7,
        timeout=100,
        max_retries=10,
    )

    if not (live_cfg_path and os.path.exists(live_cfg_path)):
        raise FileNotFoundError(f"live_mcp.json 丢失: {live_cfg_path}")
    if not (tool2mcp_path and os.path.exists(tool2mcp_path)):
        raise FileNotFoundError(f"tool2mcp.json 丢失: {tool2mcp_path}")

    all_mcp_config = load_mcp_configs_from_live_config(live_cfg_path)
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping(tool2mcp_path)

    # 规范化 live_mcp 中的 Python 路径（只处理Python命令）
    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(".py"):
            tool["args"][0] = os.path.abspath(tool["args"][0])

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
        "attack_mode": False,   # 标明是基线
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

# ========== ▲▲▲ 引入“函数化执行”实现结束 ▲▲▲ ==========

# 使用相对路径导入而非硬编码绝对路径
sys.path.append('.')

def _convert_relative_paths_in_text(text):
    """
    在文本中查找类似 "./path/to/file" 的相对路径并转换为绝对路径
    仅转换以 ./ 或 ../ 开头的路径
    """
    if not text or not isinstance(text, str):
        return text
    
    # 匹配相对路径模式 (./ 或 ../ 开头的路径)
    # 这个正则表达式会匹配引号中的相对路径或独立的相对路径
    pattern = r'(["\']?)(\.{1,2}/[^\s"\']+)["\']?'
    
    def replace_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        # 只处理以 ./ 或 ../ 开头的路径
        if path.startswith('./') or path.startswith('../'):
            try:
                abs_path = os.path.abspath(path)
                return f'{quote}{abs_path}{quote}'
            except Exception:
                # 如果转换失败，保持原路径
                return match.group(0)
        
        return match.group(0)
    
    return re.sub(pattern, replace_path, text)


def load_dataset(file_path: str) -> List[Dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 处理 test_prompts.json / all_annotations_filter.json 格式
    if isinstance(data, list) and len(data) > 0:
        tasks = []
        for i, item in enumerate(data):
            # 转换任务描述和输入中的相对路径为绝对路径
            description = item.get("Question", "")
            input_text = item.get("Question", "")
            
            # 转换相对路径
            description = _convert_relative_paths_in_text(description)
            input_text = _convert_relative_paths_in_text(input_text)
            
            task = {
                "id": item.get("task_id", f"task-{i}"),
                "description": description,
                "input": input_text,
                "expected_tools": []
            }
            tools_str = item.get("Annotator Metadata", {}).get("Tools", "")
            if tools_str:
                tools = [tool.strip() for tool in tools_str.split('\n') if tool.strip()]
                cleaned_tools = []
                for tool in tools:
                    if '. ' in tool:
                        tool = tool.split('. ', 1)[1]
                    cleaned_tools.append(tool)
                task["expected_tools"] = cleaned_tools
            tasks.append(task)
        return tasks

    # 报告格式（如果给的是之前运行产生的 report）
    if isinstance(data, dict) and "task_details" in data:
        # 对于报告格式，我们也需要转换其中的任务路径
        task_details = data["task_details"]
        for task in task_details:
            if "description" in task:
                task["description"] = _convert_relative_paths_in_text(task["description"])
            if "input" in task:
                task["input"] = _convert_relative_paths_in_text(task["input"])
        return task_details

    raise ValueError("不支持的数据集格式")

def main():
    default_input = "datasets/all_annotations_filter.json"
    default_output = "baseline_report.json"

    parser = argparse.ArgumentParser(description="MCP-Bench 基线评测（无攻击）")
    parser.add_argument("--input", "-i", default=default_input, help=f"输入任务数据集路径 (默认: {default_input})")
    parser.add_argument("--output", "-o", default=default_output, help=f"基线评测输出文件 (默认: {default_output})")
    # 路径解析相关（可选）
    parser.add_argument("--repo-root", default=os.getenv("MCP_BENCH_ROOT"),
                        help="仓库根目录（可选；默认取 env MCP_BENCH_ROOT 或 /home/llz/MCP-Bench）")
    parser.add_argument("--live-config", default=os.getenv("LIVE_MCP_PATH"),
                        help="live_mcp.json 的绝对路径（可选，优先级最高）")
    parser.add_argument("--tool2mcp", default=os.getenv("TOOL2MCP_PATH"),
                        help="tool2mcp.json 的绝对路径（可选，优先级最高）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    # 解析配置路径
    paths = _resolve_paths(args)

    print("正在加载输入数据集...")
    dataset = load_dataset(args.input)
    print(f"成功加载 {len(dataset)} 个任务")

    print("开始基线评测（无攻击）...")
    report = asyncio.run(run_tasks_as_function(
        dataset=dataset,
        attack=False,
        attack_dataset=None,
        live_cfg_path=paths["live_cfg_path"],
        tool2mcp_path=paths["tool2mcp_path"],
    ))

    # 保存完整报告
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"完成！基线结果已保存：{args.output}")

if __name__ == "__main__":
    main()
