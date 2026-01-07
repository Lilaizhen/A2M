import json
import re
from datetime import datetime


def _pretty_json(x):
    """Format JSON for display."""
    if isinstance(x, str):
        try:
            return json.dumps(json.loads(x), ensure_ascii=False, indent=2)
        except Exception:
            return x
    return json.dumps(x, ensure_ascii=False, indent=2)


def truncate_tool_outputs(response_text: str, max_lines_per_tool: int = 10) -> str:
    """
    Trim tool output to the first few lines to avoid overlong context.
    """
    if not response_text:
        return response_text
    
    lines = response_text.split('\n')
    truncated_lines = []
    in_tool_output = False
    tool_line_count = 0
    
    for line in lines:
        if "================================== Tool Output" in line:
            in_tool_output = True
            tool_line_count = 0
            truncated_lines.append(line)
        elif in_tool_output and "==================================" in line and "Tool Output" not in line:
            in_tool_output = False
            truncated_lines.append(line)
        elif in_tool_output:
            if tool_line_count < max_lines_per_tool:
                truncated_lines.append(line)
                tool_line_count += 1
            elif tool_line_count == max_lines_per_tool:
                truncated_lines.append("... (tool output truncated, showing first {} lines)".format(max_lines_per_tool))
                tool_line_count += 1
        else:
            truncated_lines.append(line)
    
    return '\n'.join(truncated_lines)


def _now():
    """Return current timestamp as ISO string."""
    return datetime.now().isoformat(timespec="seconds")


def _as_text(x):
    """Convert a value to readable text."""
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in x)
    return _pretty_json(x)


def render_behavior_from_trace(action_trace, max_tool_out_chars=2000):
    """
    Render an action_trace into readable text for judge models.
    """
    lines = []
    for ev in action_trace:
        t = ev.get("type")
        ts = ev.get("ts", "")
        if t == "user_input":
            lines.append("="*20 + " USER INPUT " + "="*20)
            lines.append(f"Time: {ts}")
            lines.append(f"Content: {ev.get('content','')}")
        elif t == "ai_message":
            lines.append("="*20 + " AI MESSAGE " + "="*20)
            lines.append(f"Time: {ts}")
            lines.append(ev.get("content",""))
        elif t == "tool_call":
            lines.append("="*20 + " TOOL CALL " + "="*20)
            lines.append(f"Time: {ts}")
            lines.append(f"Tool: {ev.get('tool','unknown')}")
            try:
                args_txt = json.dumps(ev.get("args", {}), ensure_ascii=False, indent=2)
            except Exception:
                args_txt = str(ev.get("args", {}))
            if len(args_txt) > 800:
                args_txt = args_txt[:800] + "...(truncated)"
            lines.append(f"Args:\n{args_txt}")
        elif t == "tool_output":
            lines.append("="*20 + " TOOL OUTPUT " + "="*20)
            lines.append(f"Time: {ts}")
            lines.append(f"Tool: {ev.get('tool','unknown')}")
            out = ev.get("output", "")
            try:
                out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=2)
            except Exception:
                out = str(out)
            if isinstance(out, str) and len(out) > max_tool_out_chars:
                out = out[:max_tool_out_chars] + "...(truncated)"
            lines.append(f"Output:\n{out}")
    return "\n".join(lines)
