#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attack tool extraction script: pull tools from one result folder or batch across a base dir.
(Modified: strip the 'task_' prefix from task_id.)
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict


def process_single_result_folder(folder_path: Path) -> List[Dict]:
    """
    Core logic for a single result folder containing task_* subfolders.
    """
    folder_tools = []
    
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Warning: path does not exist or is not a directory: {folder_path}")
        return folder_tools

    print(f"Processing folder: {folder_path.name}")

    # Walk all task subfolders (task_*)
    for task_dir in folder_path.iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue

        # Strip task_ prefix, e.g., "task_10" -> "10"
        task_id = task_dir.name.replace("task_", "")
        
        best_tool = None
        best_score = -1

        # Get all iteration files for the task
        iteration_files = sorted(task_dir.glob("iteration_*.json"))

        for iter_file in iteration_files:
            try:
                with open(iter_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Get the current best tool
                current_best = data.get("current_best", {})
                if current_best and "tool" in current_best:
                    tool_data = current_best["tool"]
                    score = current_best.get("score", 0)
                    mytool_calls = current_best.get("mytool_calls", 0)

                    # Only keep results with tool calls and highest score
                    if mytool_calls > 0 and score > best_score:
                        best_tool = tool_data
                        best_score = score
            except Exception as e:
                print(f"Warning: failed to process file {iter_file}: {e}")
                continue

        # Add the best tool if found
        if best_tool:
            folder_tools.append({
                "source_folder": folder_path.name,
                "task_id": task_id,  # Store ID without the prefix
                "attack_tools": [best_tool],
                "final_score": best_score
            })
            
    return folder_tools


def extract_attack_tools(base_dir: str = None, target_path: str = None, scenario_filter: str = None) -> List[Dict]:
    """
    Entry point to extract attack tools.
    """
    all_attack_tools = []

    # Mode 1: specific folder
    if target_path:
        path = Path(target_path)
        all_attack_tools.extend(process_single_result_folder(path))
    
    # Mode 2: iterate subfolders under a base directory
    elif base_dir:
        base_path = Path(base_dir)
        if not base_path.exists():
            print(f"Error: base directory does not exist: {base_dir}")
            return []

        # Walk all result folders
        for folder in base_path.iterdir():
            if not folder.is_dir():
                continue

            # Apply scenario filter
            if scenario_filter and scenario_filter not in folder.name:
                continue

            # Process each folder
            all_attack_tools.extend(process_single_result_folder(folder))
    
    else:
        print("Error: must specify --base-dir or --target-path")

    return all_attack_tools


def main():
    parser = argparse.ArgumentParser(
        description="Extract attack tools from result folders"
    )
    
    # Two mutually exclusive path parameters
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--base-dir",
        type=str,
        help="Batch mode: base directory containing result folders (e.g., ./results_attack)"
    )
    group.add_argument(
        "--target-path",
        type=str,
        help="Single-folder mode: specific result folder path (e.g., ./results_attack/resource_waste_run1)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./attack_tools_extracted.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"],
        help="Only extract tools for a specific scenario (with --base-dir)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=4,
        help="Only keep tools with score >= this value (default: 4)"
    )

    args = parser.parse_args()

    if args.target_path:
        print(f"Extracting from specified folder: {args.target_path}")
    else:
        print(f"Scanning base directory: {args.base_dir}")

    # Extract tools
    attack_tools = extract_attack_tools(
        base_dir=args.base_dir, 
        target_path=args.target_path,
        scenario_filter=args.scenario
    )

    # Apply score filter
    if args.min_score > 0:
        original_count = len(attack_tools)
        attack_tools = [tool for tool in attack_tools if tool.get("final_score", 0) >= args.min_score]
        if len(attack_tools) < original_count:
            print(f"Filter: removed {original_count - len(attack_tools)} tools below {args.min_score}")

    if not attack_tools:
        print("❌ No attack tools matched the criteria")
        return

    # Save results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(attack_tools, f, indent=2, ensure_ascii=False)

    # Stats
    total_tools = len(attack_tools)
    avg_score = sum(tool.get("final_score", 0) for tool in attack_tools) / total_tools if total_tools > 0 else 0
    max_score = max(tool.get("final_score", 0) for tool in attack_tools) if total_tools > 0 else 0
    min_score = min(tool.get("final_score", 0) for tool in attack_tools) if total_tools > 0 else 0

    score_ge_2 = sum(1 for tool in attack_tools if tool.get("final_score", 0) >= 2)
    score_eq_4 = sum(1 for tool in attack_tools if tool.get("final_score", 0) == 4)

    print(f"\n✅ Extraction done!")
    print(f"📊 Total tools: {total_tools}")
    print(f"📊 Average score: {avg_score:.2f}")
    print(f"📊 Max score: {max_score:.2f}")
    print(f"📊 Min score: {min_score:.2f}")
    if total_tools > 0:
        print(f"📈 Scores ≥2: {score_ge_2} ({score_ge_2/total_tools*100:.1f}%)")
        print(f"⭐ Scores =4: {score_eq_4} ({score_eq_4/total_tools*100:.1f}%)")
    print(f"📄 Saved to: {args.output}")


if __name__ == "__main__":
    main()
