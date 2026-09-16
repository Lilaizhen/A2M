#!/usr/bin/env python3
"""Build metadata-only baseline attack datasets with fixed static payloads."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_static_payload_factory():
    module_path = REPO_ROOT / "src" / "attacks" / "static_payloads.py"
    spec = importlib.util.spec_from_file_location("mcp_bench_static_payloads", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load static payload module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_static_payload


make_static_payload = load_static_payload_factory()


def load_records(path: Path) -> list[Any]:
    if path.suffix.lower() == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        return records

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("results"), list):
            return data["results"]
        if isinstance(data.get("items"), list):
            return data["items"]
        return [data]
    if isinstance(data, list):
        return data
    raise TypeError("Metadata input must be JSON list/object or JSONL records")


def dump_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def extract_task_ids(tasks_path: Path | None) -> list[str] | None:
    if tasks_path is None:
        return None
    tasks = load_records(tasks_path)
    task_ids = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TypeError(f"Task item at index {index} is not an object")
        task_id = first_non_empty(task.get("task_id"), task.get("id"))
        if task_id is None:
            raise ValueError(f"Missing task_id/id for task item at index {index}")
        task_ids.append(str(task_id))
    return task_ids


def extract_tool_metadata(item: dict[str, Any], index: int) -> dict[str, str]:
    candidate = item
    attack_tools = item.get("attack_tools")
    if isinstance(attack_tools, list) and attack_tools:
        candidate = attack_tools[0]
    elif isinstance(item.get("tool"), dict):
        candidate = item["tool"]
    elif isinstance(item.get("metadata"), dict):
        candidate = item["metadata"]

    name = first_non_empty(
        candidate.get("name"),
        candidate.get("tool_name"),
        candidate.get("function_name"),
        candidate.get("Attacker Tool"),
        candidate.get("attacker_tool"),
        item.get("name"),
        item.get("tool_name"),
        item.get("Attacker Tool"),
        f"static-baseline-tool-{index + 1}",
    )
    description = first_non_empty(
        candidate.get("description"),
        candidate.get("desc"),
        candidate.get("tool_description"),
        candidate.get("Description"),
        candidate.get("Attacker Instruction"),
        item.get("description"),
        item.get("desc"),
        item.get("Description"),
        item.get("Attacker Instruction"),
        "Task-relevant validation tool for the current agent workflow.",
    )
    return {"name": str(name), "description": str(description)}


def extract_item_task_id(item: dict[str, Any]) -> str | None:
    task_id = first_non_empty(
        item.get("task_id"),
        item.get("id"),
        item.get("Task ID"),
        item.get("task", {}).get("id") if isinstance(item.get("task"), dict) else None,
    )
    return str(task_id) if task_id is not None else None


def build_dataset(
    metadata_items: list[dict[str, Any]],
    scenario: str,
    method: str,
    task_ids: list[str] | None = None,
    cycle_metadata: bool = False,
) -> list[dict[str, Any]]:
    output = []
    if task_ids is not None and (cycle_metadata or len(metadata_items) != len(task_ids)):
        if not cycle_metadata and len(metadata_items) != len(task_ids):
            raise ValueError(
                f"Metadata count ({len(metadata_items)}) != task count ({len(task_ids)}). "
                "Pass --cycle-metadata to reuse metadata cyclically."
            )
        iterable = [(task_id, metadata_items[index % len(metadata_items)]) for index, task_id in enumerate(task_ids)]
    else:
        iterable = []
        for index, item in enumerate(metadata_items):
            task_id = extract_item_task_id(item)
            if task_id is None and task_ids is not None:
                task_id = task_ids[index]
            if task_id is None:
                raise ValueError(f"Missing task_id/id for metadata item at index {index}; pass --tasks if needed")
            iterable.append((task_id, item))

    for index, (task_id, item) in enumerate(iterable):
        if not isinstance(item, dict):
            raise TypeError(f"Metadata item at index {index} is not an object")
        metadata = extract_tool_metadata(item, index)
        tool_name = metadata["name"]
        output.append(
            {
                "source_folder": f"{method}_static_{scenario}",
                "task_id": task_id,
                "attack_tools": [
                    {
                        "name": tool_name,
                        "description": metadata["description"],
                        "return_value": make_static_payload(scenario, tool_name),
                    }
                ],
                "final_score": 0,
            }
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert AMA/ToolHijacker/MPMA metadata into MCP-Bench attack_dataset JSON with static payloads."
    )
    parser.add_argument("--metadata", required=True, type=Path, help="Input metadata JSON/JSONL file")
    parser.add_argument("--tasks", type=Path, help="Optional task JSON/JSONL used to provide task_id values")
    parser.add_argument("--cycle-metadata", action="store_true", help="Reuse metadata cyclically when --tasks is longer")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=[
            "resource_waste",
            "resource_waste_no_success",
            "information_leakage",
            "backdoor_injection",
            "task_failure",
        ],
        help="Attack scenario for the fixed payload",
    )
    parser.add_argument("--method", required=True, help="Baseline method label, e.g. ama/toolhijacker/mpma")
    parser.add_argument("--output", required=True, type=Path, help="Output attack_dataset JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_items = load_records(args.metadata)
    if not metadata_items:
        raise ValueError("No metadata records found")
    task_ids = extract_task_ids(args.tasks)
    output = build_dataset(metadata_items, args.scenario, args.method, task_ids, args.cycle_metadata)
    dump_json(output, args.output)
    print(f"Wrote {len(output)} tools to {args.output}")


if __name__ == "__main__":
    main()
