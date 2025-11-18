#!/usr/bin/env python3
"""
Script to process 7 attack folders, selecting one random task from each folder
and extracting a random tool from the full_tool_collection array.
"""

import json
import os
import random
from pathlib import Path

def process_attack_folders():
    """Process 7 attack folders, selecting random tasks and tools."""
    base_path = Path("/Users/lilaizhen/g2/MCP-Bench/datasets/attack_our/backdoor")

    # Define the 7 attack folders
    attack_folders = [
        "attack10",
        "attack10 copy",
        "attack10 copy 2",
        "attack10 copy 3",
        "attack10 copy 4",
        "attack10 copy 5",
        "attack10 copy 6"
    ]

    results = []
    print("=== Processing Attack Folders ===")

    for folder_name in attack_folders:
        folder_path = base_path / folder_name
        print(f"Processing {folder_name}...")

        if not folder_path.exists():
            print(f"  Warning: {folder_name} does not exist")
            continue

        # Get all task folders (directories starting with "task_")
        task_folders = [d for d in folder_path.iterdir() if d.is_dir() and d.name.startswith("task_")]

        if not task_folders:
            print(f"  Warning: No task folders found in {folder_name}")
            continue

        # Randomly select one task folder
        selected_task = random.choice(task_folders)
        task_id = selected_task.name.replace("task_", "")
        print(f"  Selected task: {selected_task.name} (from {len(task_folders)} available)")

        # Read iteration_0.json
        iteration_file = selected_task / "iteration_0.json"
        if not iteration_file.exists():
            print(f"  Warning: iteration_0.json not found in {selected_task.name}")
            continue

        try:
            with open(iteration_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract random tool from full_tool_collection
            if "full_tool_collection" not in data or not data["full_tool_collection"]:
                print(f"  Warning: No full_tool_collection found in {selected_task.name}")
                continue

            # Select random tool from full_tool_collection
            random_tool = random.choice(data["full_tool_collection"])
            attack_tools = [random_tool]  # Wrap in array as per your format

            # Extract score from current_best if available, otherwise use 1.0
            final_score = data.get("current_best", {}).get("score", 1.0)

            result = {
                "task_id": task_id,
                "attack_tools": attack_tools,
                "final_score": final_score
            }

            results.append(result)
            print(f"  ✓ Successfully processed: task_id={task_id}, tools={len(attack_tools)}, score={final_score}")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Error processing {selected_task.name}: {e}")
            continue

    return results

def main():
    print("=== Random Attack Tool Selector ===")
    print("Processing 7 attack folders to randomly select tasks and tools...\n")

    # Process all attack folders
    results = process_attack_folders()

    print(f"\nProcessing complete. Successfully processed {len(results)} out of 7 folders.")

    # Output the final JSON array
    if results:
        print("\nFinal results:")
        json_output = json.dumps(results, indent=2)
        print(json_output)

        # Also save to file for reference
        output_file = "/Users/lilaizhen/g2/MCP-Bench/attack_random_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        return results
    else:
        print("No results generated!")
        return []

if __name__ == "__main__":
    result = main()