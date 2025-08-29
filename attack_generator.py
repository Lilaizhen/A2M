#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP-Bench 攻击工具生成器
简化版本 - 单一脚本实现
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Any

# ========== ▼▼▼ 引入“函数化执行”实现（原样整块合并） ▼▼▼ ==========

# -*- coding: utf-8 -*-
import asyncio, json as _json, os as _os, time
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback

# 你项目里的模块
from src.utils.logging_config import setup_run_logger, log_and_echo
from src.utils.tool_functions import _now, _as_text, render_behavior_from_trace
from src.mcp_client.client import LimitedMCPClient
from src.agents.agent_utils import format_agent_step
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

def _build_filtered_mcp_config(expected_tools, use_mytool, tool_to_mcp, mcp_configs, attack_tools_for_task=None):
    """只加载期望工具和可选mytool；mytool可注入攻击工具定义用于红队测试。"""
    filtered = {}
    required_servers = set()
    if expected_tools:
        for t in expected_tools:
            if t in tool_to_mcp:
                required_servers.add(tool_to_mcp[t])

    if use_mytool:
        mytool_cfg = {
            "command": "python",
            "args": [_os.path.abspath("./tools/myTool.py")],
            "transport": "stdio",
        }
        # 注入攻击工具定义（若提供）。这里仅透传，不执行本地代码。
        if attack_tools_for_task:
            # 最多注入一个，避免参数爆长
            atk = attack_tools_for_task[0]
            mytool_cfg["args"].append(_json.dumps(atk, ensure_ascii=False))
        filtered["mytool"] = mytool_cfg

    for server in required_servers:
        if server in mcp_configs:
            cfg = mcp_configs[server].copy()
            cfg.setdefault("transport", "stdio")
            if cfg["command"] == "python" and cfg.get("args") and cfg["args"][0].endswith(".py"):
                cfg["args"][0] = _os.path.abspath(cfg["args"][0])
            filtered[server] = cfg

    return filtered

async def _run_single_task(task, llm, tool_to_mcp, mcp_configs, use_mytool, attack_map):
    """运行单个任务，返回结果字典。"""
    task_id = task["id"]
    task_desc = task["description"]
    user_prompt = task["input"]
    expected_tools = task.get("expected_tools", [])
    t0 = time.time()

    # 仅为该task构建MCP配置
    filtered_config = _build_filtered_mcp_config(
        expected_tools=expected_tools,
        use_mytool=use_mytool,
        tool_to_mcp=tool_to_mcp,
        mcp_configs=mcp_configs,
        attack_tools_for_task=attack_map.get(task_id),
    )

    # 尝试枚举mytool的工具名集合，便于统计
    mytool_names = set()
    if use_mytool and "mytool" in filtered_config:
        try:
            mytool_names = await fetch_server_tool_names("mytool", filtered_config["mytool"])
        except Exception:
            mytool_names = set()

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

    # 建立Agent并流式执行
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
                # 记录工具调用元信息
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

    # 任务完成度判定
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
    use_mytool=True,
    attack_dataset=None,
    model="glm-4.5",
    api_key_env="OPENAI_API_KEY",
    api_base_env="OPENAI_API_BASE",
):
    """
    作为库函数调用的入口。
    参数
      - dataset: 任务列表，每项至少包含 id/description/input/expected_tools
      - use_mytool: 是否加载mytool
      - attack_dataset: 路径或对象；用于红队测试的恶意工具定义
      - model/api_key_env/api_base_env: LLM配置（从环境变量读取）
    返回
      - 一个汇总结果dict（与原脚本最终JSON结构一致）
    """
    load_dotenv()
    # LLM配置：从环境变量读取，避免硬编码
    api_key = os.getenv(api_key_env) or ""
    api_base = os.getenv(api_base_env) or None

    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,  # None则用默认
        model=model,
        streaming=True,
        temperature=0.7,
        timeout=100,
        max_retries=1,
    )

    all_mcp_config = load_mcp_configs_from_live_config("./configs/live_mcp.json")
    tool_to_mcp, mcp_configs = load_tool_to_mcp_mapping("./configs/tool2mcp.json")

    # 规范化live_mcp路径
    for tool in all_mcp_config.values():
        tool.setdefault("transport", "stdio")
        if tool["command"] == "python" and tool.get("args") and tool["args"][0].endswith(".py"):
            tool["args"][0] = os.path.abspath(tool["args"][0])

    attack_map = _sanitize_attack_map(attack_dataset)

    results_summary = []
    for task in dataset:
        res = await _run_single_task(task, llm, tool_to_mcp, mcp_configs, use_mytool, attack_map)
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

# ========== ▲▲▲ 引入“函数化执行”实现结束 ▲▲▲ ==========


# 添加MCP-Bench路径以便导入
sys.path.append('/home/llz/MCP-Bench')

try:
    from src.core.executor import TaskExecutor
    EXECUTOR_AVAILABLE = True
except ImportError:
    EXECUTOR_AVAILABLE = False
    print("警告: 无法导入MCP-Bench执行器，将使用模拟/函数化执行器")


class RealExecutor:
    """真实执行器包装：优先调用函数化执行（run_tasks_as_function）。
    若你更想用原 TaskExecutor，可切回注释的实现。
    """

    def __init__(self, use_mytool: bool = True):
        self.use_mytool = use_mytool

    def execute_task(self, task: Dict) -> Dict:
        """执行单个任务并返回反馈"""
        try:
            # 以函数化执行为准
            report = asyncio.run(run_tasks_as_function(
                dataset=[{
                    "id": task.get("id", task.get("task_id", "")),
                    "description": task.get("description") or task.get("Question", ""),
                    "input": task.get("input") or task.get("Question", ""),
                    "expected_tools": task.get("expected_tools", [])
                }],
                use_mytool=self.use_mytool,
                attack_dataset=None  # 生成攻击工具时不注入
            ))
            detail = report["task_details"][0] if report["task_details"] else {}
            status = "success" if detail.get("task_completed") else "failed"
            return {
                "task_id": detail.get("task_id", task.get("id", task.get("task_id", ""))),
                "status": status,
                "result": detail.get("agent_final_response", ""),
                "needed_info": ["工具名称", "工具描述", "返回值"]
            }
        except Exception as e:
            return {
                "task_id": task.get("id", task.get("task_id", "")),
                "status": "error",
                "result": f"执行错误: {str(e)}",
                "needed_info": ["工具名称", "工具描述", "返回值"]
            }

    # 如果你要改回原 TaskExecutor，使用下面的实现：
    # def __init__(self):
    #     if not EXECUTOR_AVAILABLE:
    #         raise RuntimeError("MCP-Bench执行器不可用")
    #     self.executor = TaskExecutor()
    # def execute_task(self, task: Dict) -> Dict:
    #     try:
    #         result = self.executor.execute_task_sync(task)
    #         return {
    #             "task_id": task.get("id", task.get("task_id", "")),
    #             "status": result.get("status", "unknown"),
    #             "result": result.get("result", "执行完成"),
    #             "needed_info": ["工具名称", "工具描述", "返回值"]
    #         }
    #     except Exception as e:
    #         return {
    #             "task_id": task.get("id", task.get("task_id", "")),
    #             "status": "error",
    #             "result": f"执行错误: {str(e)}",
    #             "needed_info": ["工具名称", "工具描述", "返回值"]
    #         }


class SimpleExecutor:
    """简化版执行器（用于模拟或备份）"""
    def execute_task(self, task: Dict) -> Dict:
        return {
            "task_id": task.get("id", task.get("task_id", "")),
            "status": "success",
            "result": "模拟执行结果",
            "needed_info": ["工具名称", "工具描述", "返回值"]
        }


class AttackGenerator:
    """攻击工具生成器"""

    def __init__(self, use_real_executor: bool = True):
        if use_real_executor:
            print("使用函数化真实执行器")
            self.executor = RealExecutor()
        else:
            print("使用模拟执行器")
            self.executor = SimpleExecutor()

    def load_dataset(self, file_path: str) -> List[Dict]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 处理test_prompts.json格式
        if isinstance(data, list) and len(data) > 0:
            tasks = []
            for i, item in enumerate(data):
                task = {
                    "id": item.get("task_id", f"task-{i}"),
                    "description": item.get("Question", ""),
                    "input": item.get("Question", ""),
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

        # 报告格式
        elif isinstance(data, dict) and "task_details" in data:
            return data["task_details"]
        else:
            raise ValueError("不支持的数据集格式")

    def generate_attack_tool(self, task: Dict, feedback: Dict) -> Dict:
        task_id = task.get("id", task.get("task_id", ""))
        return {
            "task_id": task_id,
            "attack_tools": [
                {
                    "name": f"malicious_{task_id.replace('-', '_')}",
                    "description": f"针对任务 {task_id} 的恶意工具",
                    "return_value": "敏感信息或误导性内容"
                }
            ]
        }

    def generate_attack_dataset(self, input_dataset: List[Dict]) -> List[Dict]:
        attack_tools = []
        for task in input_dataset:
            feedback = self.executor.execute_task(task)
            malicious_tool = self.generate_attack_tool(task, feedback)
            attack_tools.append(malicious_tool)
            print(f"已处理任务: {task.get('id', task.get('task_id', 'unknown'))}")
        return attack_tools

    def save_dataset(self, dataset: List[Dict], output_path: str):
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"攻击工具数据集已保存到: {output_path}")


def main():
    default_input = "/home/llz/MCP-Bench/datasets/test_prompts.json"
    default_output = "/home/llz/MCP-Bench/11111.json"

    parser = argparse.ArgumentParser(description="MCP-Bench 攻击工具生成器")
    parser.add_argument("--input", "-i", default=default_input, help=f"输入任务数据集路径 (默认: {default_input})")
    parser.add_argument("--output", "-o", default=default_output, help=f"输出攻击工具数据集路径 (默认: {default_output})")
    parser.add_argument("--use-simulated-executor", action="store_true", help="使用模拟执行器而不是真实执行器")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    try:
        generator = AttackGenerator(use_real_executor=not args.use_simulated_exector)  # typo fix below
    except AttributeError:
        # 修正参数名拼写
        generator = AttackGenerator(use_real_executor=not args.use_simulated_executor)

    print("正在加载输入数据集...")
    input_dataset = generator.load_dataset(args.input)
    print(f"成功加载 {len(input_dataset)} 个任务")

    print("正在生成攻击工具数据集...")
    attack_dataset = generator.generate_attack_dataset(input_dataset)

    print("正在保存攻击工具数据集...")
    generator.save_dataset(attack_dataset, args.output)

    print("处理完成!")


if __name__ == "__main__":
    main()
