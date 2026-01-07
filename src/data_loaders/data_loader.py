import json
import re
import asyncio
import os

# Import temp path manager
from src.utils.temp_path_manager import convert_relative_paths_with_temp_mapping


def _convert_relative_paths_in_text(text):
    """
    Find relative paths like "./path/to/file" in text and convert to absolute.
    Only converts paths starting with ./ or ../.
    """
    if not text or not isinstance(text, str):
        return text
    
    # Match relative path patterns (starting with ./ or ../), including quoted paths
    pattern = r'(["\']?)(\.{1,2}/[^\s"\']+)["\']?'
    
    def replace_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        # Only handle ./ or ../ prefixes
        if path.startswith('./') or path.startswith('../'):
            try:
                abs_path = os.path.abspath(path)
                return f'{quote}{abs_path}{quote}'
            except Exception:
                # Keep original path on failure
                return match.group(0)
        
        return match.group(0)
    
    return re.sub(pattern, replace_path, text)


def load_mcp_configs_from_live_config(live_config_path):
    """Load MCP configs from the live config file."""
    with open(live_config_path, "r", encoding="utf-8") as f:
        live_configs = json.load(f)
    merged_config = {}
    for item in live_configs:
        if "config" in item and "mcpServers" in item["config"]:
            servers = item["config"]["mcpServers"]
            merged_config.update(servers)
    return merged_config


def load_tool_to_mcp_mapping(tool2mcp_path):
    """Load mapping from tool name to MCP server config."""
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
    """Connect to one server and return its current tool names."""
    client = MultiServerMCPClient({server_key: server_cfg})
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout=30)
        return {t.name for t in tools}
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()


def load_dataset(data_path, task_id_for_temp_mapping=None):
    """Load dataset; optionally rewrite paths for per-task temp dirs."""
    dataset = []
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            test_prompts_data = json.load(f)
            for item in test_prompts_data:
                task_id = item.get("task_id", "")
                tools_str = item.get("Annotator Metadata", {}).get("Tools", "")
                expected_tools = []
                if tools_str:
                    tools_list = [t.strip() for t in re.sub(r"\d+\.", "", tools_str).split("\n") if t.strip()]
                    expected_tools = [t for t in tools_list if t]
                
                # Convert relative paths in description/input to absolute paths
                description = item.get("Question", "")
                input_text = item.get("Question", "")
                
                # Convert relative paths
                description = _convert_relative_paths_in_text(description)
                input_text = _convert_relative_paths_in_text(input_text)
                
                # If a task id is provided, also convert to temp-mapped paths
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
        print(f"Warning: dataset file not found {data_path}")
    except Exception as e:
        print(f"Error loading {data_path}: {e}")
    return dataset
