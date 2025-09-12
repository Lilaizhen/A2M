import json
import re
import asyncio
import os

# 导入临时路径管理器
from src.utils.temp_path_manager import convert_relative_paths_with_temp_mapping


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


def load_mcp_configs_from_live_config(live_config_path):
    """从live配置文件加载MCP配置"""
    with open(live_config_path, "r", encoding="utf-8") as f:
        live_configs = json.load(f)
    merged_config = {}
    for item in live_configs:
        if "config" in item and "mcpServers" in item["config"]:
            servers = item["config"]["mcpServers"]
            merged_config.update(servers)
    return merged_config


def load_tool_to_mcp_mapping(tool2mcp_path):
    """加载工具到MCP的映射"""
    with open(tool2mcp_path, "r", encoding="utf-8") as f:
        tool2mcp_data = json.load(f)
    
    tool_to_mcp = {}
    mcp_configs = {}
    
    for item in tool2mcp_data:
        if "config" in item and "mcpServers" in item["config"]:
            servers = item["config"]["mcpServers"]
            mcp_configs.update(servers)
            for server_name in servers.keys():
                if "tools" in item:
                    server_tools = item["tools"].get(server_name, {})
                    for tool_item in server_tools.get("tools", []):
                        tool_name = tool_item.get("name")
                        if tool_name:
                            if tool_name not in tool_to_mcp:
                                tool_to_mcp[tool_name] = []
                            tool_to_mcp[tool_name].append(server_name)
    return tool_to_mcp, mcp_configs


async def fetch_server_tool_names(server_key: str, server_cfg: dict, MultiServerMCPClient):
    """单独连接一个 server，返回其当前暴露的工具名集合"""
    client = MultiServerMCPClient({server_key: server_cfg})
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout=30)
        return {t.name for t in tools}
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()


def load_dataset(data_path, task_id_for_temp_mapping=None):
    """加载数据集，支持任务ID参数用于临时路径映射"""
    dataset = []
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            test_prompts_data = json.load(f)
            for i, item in enumerate(test_prompts_data):
                task_id = item.get("task_id", "")
                tools_str = item.get("Annotator Metadata", {}).get("Tools", "")
                expected_tools = []
                if tools_str:
                    tools_list = [t.strip() for t in re.sub(r"\d+\.", "", tools_str).split("\n") if t.strip()]
                    expected_tools = [t for t in tools_list if t]
                
                # 转换任务描述和输入中的相对路径为绝对路径
                description = item.get("Question", "")
                input_text = item.get("Question", "")
                
                # 转换相对路径
                description = _convert_relative_paths_in_text(description)
                input_text = _convert_relative_paths_in_text(input_text)
                
                # 如果提供了任务ID，则也转换为临时路径
                if task_id_for_temp_mapping:
                    description = convert_relative_paths_with_temp_mapping(description, task_id_for_temp_mapping)
                    input_text = convert_relative_paths_with_temp_mapping(input_text, task_id_for_temp_mapping)
                
                task_data = {
                    "id": task_id or f"task-{len(dataset)+1}",
                    "description": description,
                    "input": input_text,
                    "expected_tools": expected_tools,
                    "category": item.get("category", "")
                }
                dataset.append(task_data)
    except FileNotFoundError:
        print(f"警告: 未找到数据集文件 {data_path}")
    except Exception as e:
        print(f"加载 {data_path} 时出错: {e}")
    return dataset