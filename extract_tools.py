import json
import os
import random
import glob
from collections import defaultdict

def main():
    base_path = "/Users/lilaizhen/g2/MCP-Bench/datasets/attack_our/task_fail"

    # Find all iteration_0.json files
    pattern = os.path.join(base_path, "task_failure10*", "task_*", "iteration_0.json")
    iteration_files = glob.glob(pattern)

    print(f"Found {len(iteration_files)} iteration_0.json files")

    # Group files by task folder (attack10, attack10 copy, etc.)
    folders_data = defaultdict(list)

    for file_path in iteration_files:
        folder_name = file_path.split("/")[-3]  # Get folder name (attack10, attack10 copy, etc.)
        folders_data[folder_name].append(file_path)

    print(f"Found task folders: {list(folders_data.keys())}")

    # For each folder, randomly select one task and one tool from its full_tool_collection
    result = []

    for folder, files in folders_data.items():
        if not files:
            continue

        # Randomly select one iteration file from this folder
        selected_file = random.choice(files)
        print(f"Processing folder {folder}, selected file: {selected_file}")

        try:
            with open(selected_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract task_id from file path
            task_id = selected_file.split("/")[-2].replace("task_", "")

            # Check if full_tool_collection exists and has tools
            if "full_tool_collection" in data and data["full_tool_collection"]:
                # Randomly select one tool from the collection
                selected_tool = random.choice(data["full_tool_collection"])

                # Create entry following backdoor.json format
                entry = {
                    "task_id": task_id,
                    "attack_tools": [selected_tool],
                    "final_score": 1.0
                }
                result.append(entry)
                print(f"  Added tool: {selected_tool.get('name', 'unknown')}")
            else:
                print(f"  No full_tool_collection found in {selected_file}")

        except Exception as e:
            print(f"  Error processing {selected_file}: {e}")

    # Save result to JSON file
    output_file = "/Users/lilaizhen/g2/MCP-Bench/datasets/attack_our/random_tool_collection_task_fail.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nConsolidated {len(result)} tools into {output_file}")

if __name__ == "__main__":
    main()