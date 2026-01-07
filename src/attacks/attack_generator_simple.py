#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point for the simplified modular attack generator.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional
from enum import Enum


class AttackType(Enum):
    RESOURCE_WASTE = "resource_waste"  # Looping tool calls to waste resources
    TASK_FAILURE = "task_failure"      # Induce agent to fail the task
    INFORMATION_LEAKAGE = "information_leakage"  # Induce agent to leak sensitive info
    BACKDOOR_INJECTION = "backdoor_injection"  # Induce agent to inject a backdoor
    RESOURCE_WASTE_NO_SUCCESS = "resource_waste_no_success"  # Resource waste regardless of task success


class SimpleAttackGenerator:
    """Simplified attack tool generator."""

    def __init__(self, api_key: Optional[str] = None, attack_type: AttackType = AttackType.RESOURCE_WASTE):
        self.api_key = api_key
        self.attack_type = attack_type
        print(f"Initialized attack generator, attack type: {attack_type.value}")

    def generate_attack_tool(self, task: Dict) -> Dict:
        """Generate an attack tool for one task (placeholder logic)."""
        task_id = task.get("id", "unknown")
        # Strip task_ prefix if present
        if isinstance(task_id, str) and task_id.startswith("task_"):
            task_id = task_id[5:]
        return {
            "task_id": task_id,
            "attack_tools": [{
                "name": f"malicious_tool_for_{self.attack_type.value}",
                "description": f"Malicious tool for {self.attack_type.value} scenario",
                "return_value": {"result": "mock_result"}
            }],
            "final_score": 0.0
        }

    def generate_attack_dataset(self, input_dataset: List[Dict]) -> List[Dict]:
        """Generate attack tools for every task in a dataset."""
        attack_tools = []
        for task in input_dataset:
            malicious_tool = self.generate_attack_tool(task)
            attack_tools.append(malicious_tool)
            print(f"Processed task: {task.get('id', 'unknown')}")
        return attack_tools

    def load_dataset(self, file_path: str) -> List[Dict]:
        """Load a task dataset from disk."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Simplified handling: return raw data
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "task_details" in data:
            return data["task_details"]
        else:
            return [data]  # Assume single task

    def save_dataset(self, dataset: List[Dict], output_path: str):
        """Save generated attack tools dataset."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"Attack tool dataset saved to: {output_path}")


def main():
    default_input = "datasets/test_prompts.json"
    default_output = "test_modular.json"

    parser = argparse.ArgumentParser(description="MCP-Bench modular attack tool generator")
    parser.add_argument("--input", "-i", default=default_input, help=f"Input task dataset path (default: {default_input})")
    parser.add_argument("--output", "-o", default=default_output, help=f"Output attack tool dataset path (default: {default_output})")
    parser.add_argument("--attack-type", dest="attack_type", default="resource_waste",
                        choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"],
                        help="Attack scenario type (default: resource_waste)")

    args = parser.parse_args()

    # Convert attack scenario argument
    try:
        attack_type = AttackType(args.attack_type)
    except ValueError:
        print(f"Error: invalid attack scenario type: {args.attack_type}")
        sys.exit(1)

    generator = SimpleAttackGenerator(attack_type=attack_type)

    print("Loading input dataset...")
    try:
        input_dataset = generator.load_dataset(args.input)
        print(f"Loaded {len(input_dataset)} tasks")
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        sys.exit(1)

    print("Generating attack tool dataset...")
    try:
        attack_dataset = generator.generate_attack_dataset(input_dataset)
        print("Saving attack tool dataset...")
        generator.save_dataset(attack_dataset, args.output)
        print("Done!")
    except Exception as e:
        print(f"Failed to generate attack tool dataset: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
