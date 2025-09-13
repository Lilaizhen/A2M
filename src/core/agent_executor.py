import asyncio
import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from langchain_core.messages import AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.utils.tool_functions import _now, _as_text
from src.agents.agent_utils import format_agent_step
from src.utils.logging_config import log_and_echo
from src.data_loaders.data_loader import fetch_server_tool_names


# 共享的最大工具输出字符数
MAX_TOOL_OUTPUT_CHARS = 8000


def reset_annotated_data(annotated_data_path: str = "./annotated_data", annotated_data_backup_path: str = "./annotated_data_backup"):
    """
    重置annotated_data文件夹到备份状态
    """
    # 删除现有的annotated_data目录
    if os.path.exists(annotated_data_path):
        shutil.rmtree(annotated_data_path)

    # 从备份复制，确保annotated_data是干净的
    if os.path.exists(annotated_data_backup_path):
        shutil.copytree(annotated_data_backup_path, annotated_data_path)
    else:
        # 如果备份不存在，创建空的annotated_data目录
        os.makedirs(annotated_data_path, exist_ok=True)


async def run_single_task_with_agent(
    task: Dict[str, Any],
    llm: Any,
    filtered_config: Dict[str, Any],
    expected_tools: List[str],
    attack: bool = False,
    attack_tools_for_task: List[Dict] = None,
    mytool_tool_names: set = None,
    tool_lock: Optional[asyncio.Lock] = None
) -> Dict[str, Any]:
    """
    使用agent运行单个任务并返回结果
    """
    task_id = task.get("id", "")
    task_desc = task.get("description", "")
    user_prompt = task.get("input", task.get("Question", ""))
    t0 = asyncio.get_event_loop().time()

    # 获取当前任务的攻击工具名称，用于统计
    attack_tool_names = set()
    if attack and attack_tools_for_task:
        attack_tool_names = {tool.get("name") for tool in attack_tools_for_task if tool.get("name")}

    # 合并mytool服务器本身的工具名称和攻击工具名称
    all_mytool_names = set()
    if mytool_tool_names:
        all_mytool_names = mytool_tool_names.union(attack_tool_names)

    # 加载MCP工具
    try:
        from src.mcp_client.client import LimitedMCPClient
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
            "execution_time_seconds": asyncio.get_event_loop().time() - t0,
            "total_tool_calls": 0,
            "mytool_calls": 0,
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "action_trace": [{"ts": _now(), "type": "user_input", "content": user_prompt}],
        }

    # 建立Agent并流式执行
    final_response = ""
    action_trace = [{"ts": _now(), "type": "user_input", "content": user_prompt}]
    token_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    current_tool_execution = None

    agent = create_react_agent(llm, tools, checkpointer=MemorySaver())
    config = {"recursion_limit": 100, "configurable": {"thread_id": f"task-{task_id}"}}
    user_input = {"role": "user", "content": user_prompt}

    async def _drain_stream():
        nonlocal final_response, action_trace, current_tool_execution
        async for step in agent.astream({"messages": [user_input]}, config, stream_mode="values"):
            last_message = step["messages"][-1]
            pretty = format_agent_step(last_message)
            log_and_echo(pretty)

            # 1) 工具输出
            if isinstance(last_message, ToolMessage):
                tool_output_text = _as_text(last_message.content)
                if isinstance(tool_output_text, str) and len(tool_output_text) > MAX_TOOL_OUTPUT_CHARS:
                    tool_output_text = tool_output_text[:MAX_TOOL_OUTPUT_CHARS] + "...(内容已截断)"
                action_trace.append({
                    "ts": _now(),
                    "type": "tool_output",
                    "tool": last_message.name,
                    "output": tool_output_text
                })
                # 清除当前工具执行状态
                current_tool_execution = None
                continue

            # 2) AI 消息 + 其中的工具调用
            if isinstance(last_message, AIMessage):
                content_text = _as_text(last_message.content).strip()
                if content_text:
                    final_response = content_text
                    action_trace.append({
                        "ts": _now(),
                        "type": "ai_message",
                        "content": content_text
                    })

                # 获取所有工具调用
                tool_calls = getattr(last_message, "tool_calls", None) or last_message.additional_kwargs.get("tool_calls", [])

                # 使用锁确保一次只处理一个工具调用
                if tool_lock:
                    async with tool_lock:
                        # 如果有正在执行的工具，等待其完成
                        while current_tool_execution is not None:
                            await asyncio.sleep(0.1)

                        # 只处理第一个工具调用
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
                            action_trace.append({
                                "ts": _now(),
                                "type": "tool_call",
                                "tool": name,
                                "args": args
                            })
                            tool_call_msg = {"type": "tool_call", "tool_name": name, "tool_input": args}
                            tc_pretty = format_agent_step(tool_call_msg)
                            log_and_echo(tc_pretty)
                            # 设置当前正在执行的工具
                            current_tool_execution = name
                else:
                    # 不使用锁的简化版本
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
                        action_trace.append({
                            "ts": _now(),
                            "type": "tool_call",
                            "tool": name,
                            "args": args
                        })
                        tool_call_msg = {"type": "tool_call", "tool_name": name, "tool_input": args}
                        tc_pretty = format_agent_step(tool_call_msg)
                        log_and_echo(tc_pretty)
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

                if tool_lock:
                    # 使用锁确保一次只处理一个工具调用
                    async with tool_lock:
                        # 如果有正在执行的工具，等待其完成
                        while current_tool_execution is not None:
                            await asyncio.sleep(0.1)

                        action_trace.append({
                            "ts": _now(),
                            "type": "tool_call",
                            "tool": name,
                            "args": args
                        })
                        tool_call_msg = {"type": "tool_call", "tool_name": name, "tool_input": args}
                        tc_pretty = format_agent_step(tool_call_msg)
                        log_and_echo(tc_pretty)
                        # 设置当前正在执行的工具
                        current_tool_execution = name
                else:
                    # 不使用锁的简化版本
                    action_trace.append({
                        "ts": _now(),
                        "type": "tool_call",
                        "tool": name,
                        "args": args
                    })
                    tool_call_msg = {"type": "tool_call", "tool_name": name, "tool_input": args}
                    tc_pretty = format_agent_step(tool_call_msg)
                    log_and_echo(tc_pretty)
                return

    async def _drain():
        nonlocal final_response
        async for step in agent.astream({"messages": [{"role": "user", "content": user_prompt}]}, config, stream_mode="values"):
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
                            args = json.loads(args)
                    except Exception:
                        pass
                    action_trace.append({"ts": _now(), "type": "tool_call", "tool": name, "args": args})

    # 根据需要选择适当的drain函数
    drain_function = _drain_stream if tool_lock else _drain

    try:
        with get_openai_callback() as cb:
            await asyncio.wait_for(drain_function(), timeout=500)
            token_usage = {
                "total_tokens": cb.total_tokens,
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
            }
    except asyncio.TimeoutError:
        action_trace.append({"ts": _now(), "type": "ai_message", "content": "Agent 执行超时（>500s）"})

    total_tool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call")
    mytool_calls = sum(1 for x in action_trace if x.get("type") == "tool_call" and x.get("tool") in all_mytool_names)

    return {
        "task_id": task_id,
        "input": user_prompt,
        "expected_tools": expected_tools,
        "agent_final_response": final_response,
        "task_completed": False,  # 需要在外部判断
        "completion_reason": {},  # 需要在外部判断
        "execution_time_seconds": asyncio.get_event_loop().time() - t0,
        "total_tool_calls": total_tool_calls,
        "mytool_calls": mytool_calls,
        "token_usage": token_usage,
        "action_trace": action_trace,
    }