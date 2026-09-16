import asyncio
import inspect
from langchain_mcp_adapters.client import MultiServerMCPClient


def create_tool_wrapper(
    original_func,
    max_length,
    max_list_length=100,
    max_category_items=20,
    timeout=30,
    tool_name=None,
    fides_guard=None,
):
    """创建带超时和可选 FIDES-style 防御的工具函数包装器"""
    async def wrapped_func(*args, **kwargs):
        tool_args = kwargs if kwargs else (args[0] if len(args) == 1 else list(args))
        current_tool_name = tool_name or getattr(original_func, "__name__", "unknown_tool")

        if fides_guard is not None:
            decision = fides_guard.before_tool_call(current_tool_name, tool_args)
            if not decision.allowed:
                return {
                    "fides_blocked": True,
                    "tool": current_tool_name,
                    "policy": decision.policy,
                    "reason": decision.reason,
                }

        try:
            result = await asyncio.wait_for(original_func(*args, **kwargs), timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"工具调用超时（>{timeout}s）"}

        result = limit_result_length(result, max_length, max_list_length, max_category_items)
        if fides_guard is not None:
            result = fides_guard.after_tool_call(current_tool_name, tool_args, result)
        return result
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
    except Exception:
        return result


def _is_coordinate_list(lst):
    """判断是否为坐标列表"""
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
    """采样坐标列表"""
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
    """智能截断列表"""
    if len(lst) <= max_length:
        return lst
    truncated = lst[:max_length - 1]
    truncated.append({
        "type": "info",
        "text": f"...(列表已截断，原始长度: {len(lst)}, 已截断: {len(lst) - max_length + 1})"
    })
    return truncated


class LimitedMCPClient:
    def __init__(
        self,
        config,
        max_response_length=5000,
        max_list_length=100,
        max_category_items=20,
        timeout=30,
        fides_guard=None,
    ):
        self.client = MultiServerMCPClient(config)
        self.max_length = max_response_length
        self.max_list_length = max_list_length
        self.max_category_items = max_category_items
        self.timeout = timeout
        self.fides_guard = fides_guard
    
    async def get_tools(self):
        # get_tools 本身也加超时，避免卡在握手阶段
        tools = await asyncio.wait_for(self.client.get_tools(), timeout=self.timeout)
        for tool in tools:
            original_func = tool.func
            tool.func = create_tool_wrapper(
                original_func,
                self.max_length,
                self.max_list_length,
                self.max_category_items,
                timeout=self.timeout,
                tool_name=getattr(tool, "name", None),
                fides_guard=self.fides_guard,
            )
        return tools

    async def close(self):
        close = getattr(self.client, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result
