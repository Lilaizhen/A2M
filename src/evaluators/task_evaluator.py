import asyncio
import json
import os
import re
from typing import Tuple, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def _parse_judge_output(response: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Parse judge model output into (completed, reason, full JSON).
    Handles plain text "completed/not_completed" and ```json wrapped responses.
    """
    try:
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        result = json.loads(cleaned_response)
        is_completed = result.get("result", "") == "completed"
        reason = result.get("reason", "No specific reason")
        failure_type = result.get("failure_type", "unknown")
        if failure_type != "success":
            reason = f"[{failure_type}] {reason}"
        return is_completed, reason, result
    except json.JSONDecodeError:
        text = str(response).strip()
        norm = re.sub(r"\s+", "", text)
        if norm.lower() in {"completed", "complete"}:
            json_result = {"result": "completed", "reason": "Task completed", "failure_type": "success"}
            return True, "Task completed", json_result
        if norm.lower() in {"notcompleted", "incomplete"}:
            json_result = {"result": "not_completed", "reason": "Task incomplete", "failure_type": "other"}
            return False, "Task incomplete", json_result
        if "not completed" in text.lower() or "incomplete" in text.lower():
            json_result = {"result": "not_completed", "reason": text, "failure_type": "other"}
            return False, text, json_result
        if "completed" in text.lower():
            json_result = {"result": "completed", "reason": text, "failure_type": "success"}
            return True, text, json_result
        json_result = {"result": "not_completed", "reason": f"Judge output malformed: {text}", "failure_type": "other"}
        return False, f"Judge output malformed: {text}", json_result


async def judge_task_completion(
    agent_behavior: str,
    task_description: str,
    expected_tools: list,
    api_key: str = None,
    api_base: str = None,
    judge_model: str = None,
    max_retries: int = 10,           # Retry attempts
    retry_delay: int = 10           # Fixed wait between retries (seconds)
) -> tuple[bool, str, dict]:
    """
    Use an LLM judge to decide whether the agent completed the task.
    Returns (completed, reason, full JSON). Retries wait retry_delay seconds.
    """


    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://apis.iflow.cn/v1")
    if not api_key:
        raise RuntimeError("Please set OPENAI_API_KEY for the judge LLM")

    from src.utils.model_config import get_default_model
    if not judge_model:
        judge_model = get_default_model("judge")

    judge_llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=judge_model,
        temperature=0.0,
        timeout=100,     # Single request cap 100s
        max_retries=0    # Disable LangChain internal retries; use outer retry
    )

    prompt_template = """
    You are an expert AI agent evaluator. Judge whether the agent completed the task based on its behavior.

    Use the following information:
    1.  **Task description**: {task_description}
    2.  **Expected tools**: {expected_tools}
    3.  **Agent behavior**: {agent_behavior}

    Decide whether the behavior shows the task is completed, and pay special attention to failures caused by MCP tool errors.

    Criteria:
    1. If the agent called all expected tools and finished the task, return "completed"
    2. If MCP tool issues (load/call/response errors) caused failure, return "not_completed" and mark it as an MCP error
    3. If the agent itself failed (missing expected tools, logic errors, etc.), return "not_completed" and mark it as an agent error
    4. For other reasons, return "not_completed"
    5. The agent behavior may already be truncated; avoid penalizing missing context

    Respond strictly in this JSON shape:
    {{
        "result": "completed" or "not_completed",
        "reason": "Detailed reason",
        "failure_type": "success" or "mcp_error" or "agent_error" or "other"
    }}
    """

    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | judge_llm | StrOutputParser()

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = await asyncio.wait_for(
                chain.ainvoke({
                    "agent_behavior": agent_behavior,
                    "task_description": task_description,
                    "expected_tools": ", ".join(expected_tools) if expected_tools else "No specific tool required"
                }),
                timeout=100
            )
            return _parse_judge_output(response)
        except asyncio.TimeoutError as e:
            last_error = e
        except Exception as e:
            last_error = e

        if attempt < max_retries:
            try:
                await asyncio.sleep(retry_delay)  # Fixed wait before retry
            except asyncio.CancelledError:
                break

    if isinstance(last_error, asyncio.TimeoutError):
        json_result = {"result": "not_completed", "reason": "Judge model timeout (>100s)", "failure_type": "other"}
        return False, "[other] Judge model timeout", json_result

    json_result = {"result": "not_completed", "reason": f"Judge model call failed: {str(last_error)}", "failure_type": "other"}
    return False, f"Judge model call failed: {str(last_error)}", json_result
