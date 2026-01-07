import asyncio
import argparse
import os
import shutil
import json
from main_module import main as main_function
from src.data_loaders.data_loader import load_dataset
from src.utils.model_config import resolve_model, get_default_model

def reset_annotated_data():
    """Reset the annotated_data folder back to the backup state."""
    annotated_data_path = os.path.join(os.getcwd(), "annotated_data")
    annotated_data_backup_path = os.path.join(os.getcwd(), "annotated_data_backup")
    
    if os.path.exists(annotated_data_path):
        shutil.rmtree(annotated_data_path)
    if os.path.exists(annotated_data_backup_path):
        shutil.copytree(annotated_data_backup_path, annotated_data_path)
    else:
        os.makedirs(annotated_data_path, exist_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Select dataset: all, test, filter
    parser.add_argument(
        "--dataset",
        choices=["all", "test", "filter"],
        default="all",
        help=(
            "Choose dataset:\n"
            "all=./datasets/all_annotations.json (default)\n"
            "test=./datasets/test_prompts.json\n"
            "filter=./datasets/all_annotations_filter.json"
        )
    )
    parser.add_argument("--attack", action="store_true", help="Enable attack mode (mytool MCP server)")
    parser.add_argument("--attack-dataset", type=str, help="Path to attack dataset")
    parser.add_argument("--attack-scenario", type=str, choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"], default="resource_waste", help="Attack scenario type (default: resource_waste)")
    parser.add_argument("--model", type=str, default=None, help="Model name or alias to use")
    parser.add_argument("--judge-model", type=str, default=None, help="Judge model name")
    args = parser.parse_args()

    # Dataset path mapping
    if args.dataset == "test":
        data_path = "./datasets/test_prompts.json"
    elif args.dataset == "filter":
        data_path = "./datasets/all_annotations_filter.json"
    else:  # default all
        data_path = "./datasets/all_annotations.json"

    dataset = load_dataset(data_path)

    # If an attack dataset is provided, only run tasks present in that dataset
    filtered_dataset = dataset
    if args.attack and args.attack_dataset:
        try:
            with open(args.attack_dataset, 'r', encoding='utf-8') as f:
                attack_data = json.load(f)

            # Extract task IDs from attack dataset
            attack_task_ids = set()
            if isinstance(attack_data, list):
                for item in attack_data:
                    if 'task_id' in item:
                        task_id = item['task_id']
                        # Handle potential 'task_' prefix
                        if task_id.startswith('task_'):
                            task_id = task_id[5:]  # remove prefix
                        attack_task_ids.add(task_id)
            elif isinstance(attack_data, dict) and 'attack_tools' in attack_data:
                # Single task case
                if 'task_id' in attack_data:
                    task_id = attack_data['task_id']
                    if task_id.startswith('task_'):
                        task_id = task_id[5:]
                    attack_task_ids.add(task_id)

            # Filter dataset to keep only tasks in attack dataset
            if attack_task_ids:
                filtered_dataset = [task for task in dataset if task.get('id') in attack_task_ids]
                print(f"\n" + "=" * 60)
                print("🔍 Attack dataset filter result:")
                print(f"   Original dataset: {len(dataset)} tasks")
                print(f"   Attack dataset: {len(attack_task_ids)} tasks")
                print(f"   To be executed: {len(filtered_dataset)} tasks")
                if len(filtered_dataset) < len(attack_task_ids):
                    missing_tasks = attack_task_ids - set(task.get('id') for task in filtered_dataset)
                    print(f"   Missing task IDs: {missing_tasks}")
                print("=" * 60 + "\n")
            else:
                print("⚠️ Warning: Attack dataset format invalid, running all tasks")
                filtered_dataset = dataset
        except Exception as e:
            print(f"⚠️ Warning: Failed to load attack dataset: {e}, running all tasks")
            filtered_dataset = dataset

    if filtered_dataset:
        # Resolve model names
        model_name = resolve_model(args.model) if args.model else get_default_model("agent")
        judge_model = resolve_model(args.judge_model) if args.judge_model else get_default_model("judge")

        # Reset annotated_data folder
        reset_annotated_data()
        asyncio.run(main_function(
            filtered_dataset,
            attack=args.attack,
            attack_dataset_path=args.attack_dataset,
            attack_scenario=args.attack_scenario,
            model_name=model_name,
            judge_model=judge_model,
            dataset_type=args.dataset
        ))
    else:
        print("Error: no valid dataset files found")
