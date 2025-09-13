import asyncio
import json
from typing import Dict, List, Any, Optional
from langchain_core.messages import AIMessage, ToolMessage
from langchain_community.callbacks.manager import get_openai_callback
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.utils.tool_functions import _now, _as_text
from src.agents.agent_utils import format_agent_step
from src.utils.logging_config import log_and_echo


# 共享的最大工具输出字符数
MAX_TOOL_OUTPUT_CHARS = 8000


async def run_agent_with_streaming(
    llm: Any,
    tools: List[Any],
    task_id: str,
    user_prompt: str,
    use_tool_lock: bool = True
) -> Dict[str, Any]:
    """
    使用流式执行运行agent并返回结果

    Args:
        llm: LLM实例
        tools: 工具列表
        task_id: 任务ID
        user_prompt: 用户提示
        use_tool_lock: 是否使用工具锁机制（默认True）

    Returns:
        包含执行结果的字典
    """
    # 建立Agent并流式执行
    final_response = ""
    action_trace = [{"ts": _now(), "type": "user_input", "content": user_prompt}]
    token_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    current_tool_execution = None

    agent = create_react_agent(llm, tools, checkpointer=MemorySaver())
    config = {"recursion_limit": 100, "configurable": {"thread_id": f"task-{task_id}"}}
    user_input = {"role": "user", "content": user_prompt}

    # 创建工具锁（如果需要）
    tool_lock = asyncio.Lock() if use_tool_lock else None

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

    async def _drain_simple():
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
    drain_function = _drain_stream if use_tool_lock else _drain_simple

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

    return {
        "final_response": final_response,
        "action_trace": action_trace,
        "token_usage": token_usage,
    }


async def run_agent_simple(
    llm: Any,
    tools: List[Any],
    task_id: str,
    user_prompt: str
) -> Dict[str, Any]:
    """
    使用简单执行运行agent并返回结果（不带流式处理和工具锁）

    Args:
        llm: LLM实例
        tools: 工具列表
        task_id: 任务ID
        user_prompt: 用户提示

    Returns:
        包含执行结果的字典
    """
    # 建立Agent并执行
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
                            args = json.loads(args)
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

    return {
        "final_response": final_response,
        "action_trace": action_trace,
        "token_usage": token_usage,
    }