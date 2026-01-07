#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example usage for the modular attack generator.
"""

import sys
import os

# Add project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.attacks import AttackGenerator, AttackType

def main():
    """Demonstrate how to use the modular attack generator."""
    print("=== MCP-Bench Modular Attack Generator Example ===")

    # Resource-waste attack generator
    print("\n1. Create resource-waste attack generator...")
    resource_waste_generator = AttackGenerator(attack_type=AttackType.RESOURCE_WASTE)
    print("   Created resource-waste attack generator")

    # Task-failure attack generator
    print("\n2. Create task-failure attack generator...")
    task_failure_generator = AttackGenerator(attack_type=AttackType.TASK_FAILURE)
    print("   Created task-failure attack generator")

    # Info-leak attack generator
    print("\n3. Create information-leak attack generator...")
    information_leakage_generator = AttackGenerator(attack_type=AttackType.INFORMATION_LEAKAGE)
    print("   Created information-leak attack generator")

    # Sample task data
    sample_task = {
        "id": "task-001",
        "description": "Analyze a document and extract key information",
        "input": "Please analyze this technical document and summarize the main points",
        "expected_tools": ["document_analyzer", "summarizer"]
    }

    # Generate examples for different attack scenarios
    print("\n4. Generate attack tools for scenarios...")

    try:
        print("   Generating resource-waste attack tool...")
        resource_tool = resource_waste_generator.generate_attack_tool(sample_task)
        print(f"   Generated resource-waste attack tool: {resource_tool['attack_tools'][0]['name']}")

        print("   Generating task-failure attack tool...")
        failure_tool = task_failure_generator.generate_attack_tool(sample_task)
        print(f"   Generated task-failure attack tool: {failure_tool['attack_tools'][0]['name']}")

        print("   Generating information-leak attack tool...")
        information_leakage_tool = information_leakage_generator.generate_attack_tool(sample_task)
        print(f"   Generated information-leak attack tool: {information_leakage_tool['attack_tools'][0]['name']}")

    except Exception as e:
        print(f"   Failed to generate attack tool: {e}")

    print("\n=== Modular advantages ===")
    print("1. Each attack scenario is isolated for easy maintenance/extension")
    print("2. Fitness scoring is encapsulated and swappable")
    print("3. Core execution is separated from scenario generation")
    print("4. Clear structure makes it easy to read and modify")

    print("\n=== Usage tips ===")
    print("1. Pick an attack type that matches your needs")
    print("2. Subclass and override methods to customize behavior")
    print("3. Add new scenarios easily with the modular layout")

if __name__ == "__main__":
    main()
