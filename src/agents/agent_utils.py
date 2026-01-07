from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json


def _pretty_json(x):
    """Format JSON output for readability."""
    if isinstance(x, str):
        try:
            return json.dumps(json.loads(x), ensure_ascii=False, indent=2)
        except Exception:
            return x
    return json.dumps(x, ensure_ascii=False, indent=2)


def format_agent_step(step_message):
    """Format agent step messages for logging/printing."""
    if isinstance(step_message, HumanMessage):
        role_header = "================================== Human Input =================================="
        return f"\n{role_header}\n{step_message.content}\n"
    elif isinstance(step_message, AIMessage):
        role_header = "================================== AI Message ==================================="
        content = step_message.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        else:
            text = str(content)
        return f"\n{role_header}\n{text}\n"
    elif isinstance(step_message, ToolMessage):
        role_header = f"================================== Tool Output ({step_message.name}) =================================="
        content = step_message.content
        return f"\n{role_header}\n{content if isinstance(content, str) else _pretty_json(content)}\n"
    elif isinstance(step_message, dict) and step_message.get("type") == "tool_call":
        role_header = "================================== Tool Call ===================================="
        name = step_message.get("tool_name", "unknown_tool")
        args = step_message.get("tool_input", {})
        return f"\n{role_header}\nTool Name: {name}\nArguments: {_pretty_json(args)}\n"
    else:
        role_header = "================================== Unknown Message ================================"
        return f"\n{role_header}\n{getattr(step_message, 'content', '')}\n"
