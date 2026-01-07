import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


def create_tool_wrapper(original_func, max_length, max_list_length=100, max_category_items=20, timeout=30):
    """Create a tool wrapper that enforces timeout and output truncation."""
    async def wrapped_func(*args, **kwargs):
        try:
            result = await asyncio.wait_for(original_func(*args, **kwargs), timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Tool call timed out (>{timeout}s)"}
        return limit_result_length(result, max_length, max_list_length, max_category_items)
    return wrapped_func


def limit_result_length(result, max_length, max_list_length=100, max_category_items=20):
    """
    Limit returned content length while keeping structure intact.
    """
    try:
        if isinstance(result, str):
            if len(result) > max_length:
                return result[:max_length] + "...(content truncated)"
            return result
        elif isinstance(result, dict):
            result = result.copy()
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    result[key] = limit_result_length(value, max_length, max_list_length, max_category_items)
                elif isinstance(value, str) and len(value) > max_length:
                    result[key] = value[:max_length] + "...(content truncated)"
            if 'categories' in result and isinstance(result['categories'], dict):
                for category_key, category_value in result['categories'].items():
                    if isinstance(category_value, dict):
                        for subcategory_key, subcategory_value in category_value.items():
                            if isinstance(subcategory_value, list) and len(subcategory_value) > max_category_items:
                                truncated_list = subcategory_value[:max_category_items]
                                truncated_list.append({
                                    "id": "truncated",
                                    "name": f"...{len(subcategory_value) - max_category_items} more items not shown...",
                                    "type": "info",
                                    "tags": {
                                        "note": f"Original list has {len(subcategory_value)} items; truncated to keep response concise"
                                    }
                                })
                                result['categories'][category_key][subcategory_key] = truncated_list
            if 'content' in result:
                if isinstance(result['content'], str):
                    if len(result['content']) > max_length:
                        result['content'] = result['content'][:max_length] + "...(content truncated)"
                elif isinstance(result['content'], list):
                    if len(result['content']) > 50:
                        result['content'] = result['content'][:50] + [
                            {"type": "text", "text": f"...(content list truncated, {len(result['content']) - 50} more items)"}
                        ]
                    else:
                        total_length = 0
                        for item in result['content']:
                            if isinstance(item, dict) and 'text' in item:
                                text = item['text']
                                if isinstance(text, str):
                                    remaining_length = max_length - total_length
                                    if remaining_length <= 0:
                                        item['text'] = "...(content truncated)"
                                        break
                                    elif len(text) > remaining_length:
                                        item['text'] = text[:remaining_length] + "...(content truncated)"
                                    total_length += len(item['text'])
        elif isinstance(result, list):
            if len(result) > max_list_length:
                if _is_coordinate_list(result):
                    sampled_result = _sample_coordinate_list(result, max_list_length)
                    sampled_result.append({
                        "type": "info",
                        "text": f"...(coordinate list sampled, original length: {len(result)}, after sampling: {len(sampled_result)})"
                    })
                    result = sampled_result
                else:
                    result = _smart_truncate_list(result, max_list_length)
            else:
                for i, item in enumerate(result):
                    if isinstance(item, (dict, list)):
                        result[i] = limit_result_length(item, max_length, max_list_length, max_category_items)
                    elif isinstance(item, str) and len(item) > max_length:
                        result[i] = item[:max_length] + "...(content truncated)"
        return result
    except Exception:
        return result


def _is_coordinate_list(lst):
    """Check whether list looks like coordinates."""
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
    """Sample a coordinate list to a bounded length."""
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
    """Truncate list and append info entry when shortened."""
    if len(lst) <= max_length:
        return lst
    truncated = lst[:max_length - 1]
    truncated.append({
        "type": "info",
        "text": f"...(list truncated, original length: {len(lst)}, removed: {len(lst) - max_length + 1})"
    })
    return truncated


class LimitedMCPClient:
    def __init__(self, config, max_response_length=5000, max_list_length=100, max_category_items=20, timeout=30):
        self.client = MultiServerMCPClient(config)
        self.max_length = max_response_length
        self.max_list_length = max_list_length
        self.max_category_items = max_category_items
        self.timeout = timeout
    
    async def get_tools(self):
        # Apply timeout to get_tools itself to avoid hanging during handshake
        tools = await asyncio.wait_for(self.client.get_tools(), timeout=self.timeout)
        for tool in tools:
            original_func = tool.func
            tool.func = create_tool_wrapper(
                original_func, 
                self.max_length, 
                self.max_list_length, 
                self.max_category_items,
                timeout=self.timeout
            )
        return tools
