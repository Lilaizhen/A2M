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
    解析裁判模型输出为 (是否完成, 原因, 完整JSON)
    兼容纯文本“完成/未完成”和```json 包裹的响应
    """
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


async def judge_task_completion(
    agent_behavior: str,
    task_description: str,
    expected_tools: list,
    api_key: str = None,
    api_base: str = None,
    judge_model: str = None,
    max_retries: int = 10,           # 新增：失败重试次数
    retry_delay: int = 10           # 新增：固定重试等待时间（秒）
) -> tuple[bool, str, dict]:
    """
    使用 LLM 判断 Agent 是否成功完成任务，并返回 (是否完成, 原因, 完整JSON)
    失败会固定等待 retry_delay 秒后重试
    """


    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://apis.iflow.cn/v1")
    if not api_key:
        raise RuntimeError("请为裁判 LLM 设置 OPENAI_API_KEY 环境变量")

    from src.utils.model_config import get_default_model
    if not judge_model:
        judge_model = get_default_model("judge")

    judge_llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base=api_base,
        model=judge_model,
        temperature=0.0,
        timeout=100,     # 单次请求上限100s
        max_retries=0    # 关闭 LangChain 内部重试，使用外层重试
    )

    prompt_template = """
    你是一个专业的 AI Agent 任务评估员。你的任务是根据 Agent 的实际行为，判断其是否成功完成了指定的任务。

    请严格按照以下信息进行判断：
    1.  **任务描述**: {task_description}
    2.  **预期工具**: {expected_tools}
    3.  **Agent 的实际行为**: {agent_behavior}

    请判断"Agent 的实际行为"是否表明任务已成功完成，并特别注意是否因为MCP工具异常导致任务失败。

    判断标准：
    1. 如果Agent调用的工具中包含所有预期工具，并且完成任务，返回 "完成"
    2. 如果因为MCP工具异常（如工具无法加载、工具调用失败、工具返回错误等）导致任务失败，返回 "未完成" 并在原因中说明是MCP异常
    3. 如果Agent本身执行有问题（如没有调用所有预期工具、逻辑错误等）导致任务失败，返回 "未完成" 并在原因中说明是Agent问题
    4. 其他原因导致的失败，返回 "未完成"
    5. Agent 的实际行为是已经截断后的

    你的回答必须严格按照以下 JSON 格式：
    {{
        "result": "完成" 或 "未完成",
        "reason": "具体原因说明",
        "failure_type": "success" 或 "mcp_error" 或 "agent_error" 或 "other"
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
                    "expected_tools": ", ".join(expected_tools) if expected_tools else "无特定工具要求"
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
                await asyncio.sleep(retry_delay)  # 固定等待10秒
            except asyncio.CancelledError:
                break

    if isinstance(last_error, asyncio.TimeoutError):
        json_result = {"result": "未完成", "reason": "裁判模型超时（>100s）", "failure_type": "other"}
        return False, "[other] 裁判模型超时", json_result

    json_result = {"result": "未完成", "reason": f"裁判模型调用失败: {str(last_error)}", "failure_type": "other"}
    return False, f"裁判模型调用失败: {str(last_error)}", json_result
