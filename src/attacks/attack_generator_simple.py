#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版模块化攻击生成器主入口文件
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional
from enum import Enum


class AttackType(Enum):
    RESOURCE_WASTE = "resource_waste"  # 工具循环调用 资源浪费
    TASK_FAILURE = "task_failure"      # 诱导agent调用 使任务执行失败
    INFORMATION_LEAKAGE = "information_leakage"  # 诱导agent泄漏敏感信息
    BACKDOOR_INJECTION = "backdoor_injection"  # 诱导agent注入后门
    RESOURCE_WASTE_NO_SUCCESS = "resource_waste_no_success"  # 工具循环调用 资源浪费 但不考虑任务成功


class SimpleAttackGenerator:
    """简化版攻击工具生成器"""

    def __init__(self, api_key: Optional[str] = None, attack_type: AttackType = AttackType.RESOURCE_WASTE):
        self.api_key = api_key
        self.attack_type = attack_type
        print(f"初始化攻击生成器，攻击类型: {attack_type.value}")

    def generate_attack_tool(self, task: Dict) -> Dict:
        """为单个任务生成攻击工具"""
        # 这里应该是实际的攻击工具生成逻辑
        # 简化版只返回一个示例结构
        return {
            "task_id": task.get("id", "unknown"),
            "attack_tools": [{
                "name": f"malicious_tool_for_{self.attack_type.value}",
                "description": f"针对{self.attack_type.value}场景的恶意工具",
                "return_value": {"result": "mock_result"}
            }],
            "final_score": 0.0
        }

    def generate_attack_dataset(self, input_dataset: List[Dict]) -> List[Dict]:
        """为数据集中的所有任务生成攻击工具"""
        attack_tools = []
        for task in input_dataset:
            malicious_tool = self.generate_attack_tool(task)
            attack_tools.append(malicious_tool)
            print(f"已处理任务: {task.get('id', 'unknown')}")
        return attack_tools

    def load_dataset(self, file_path: str) -> List[Dict]:
        """加载任务数据集"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 简化处理，直接返回数据
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "task_details" in data:
            return data["task_details"]
        else:
            return [data]  # 假设是单个任务

    def save_dataset(self, dataset: List[Dict], output_path: str):
        """保存攻击工具数据集"""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"攻击工具数据集已保存到: {output_path}")


def main():
    default_input = "datasets/test_prompts.json"
    default_output = "test_modular.json"

    parser = argparse.ArgumentParser(description="MCP-Bench 模块化攻击工具生成器")
    parser.add_argument("--input", "-i", default=default_input, help=f"输入任务数据集路径 (默认: {default_input})")
    parser.add_argument("--output", "-o", default=default_output, help=f"输出攻击工具数据集路径 (默认: {default_output})")
    parser.add_argument("--attack-type", dest="attack_type", default="resource_waste",
                        choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"],
                        help="攻击场景类型 (默认: resource_waste)")

    args = parser.parse_args()

    # 转换攻击场景参数
    try:
        attack_type = AttackType(args.attack_type)
    except ValueError:
        print(f"错误: 无效的攻击场景类型: {args.attack_type}")
        sys.exit(1)

    generator = SimpleAttackGenerator(attack_type=attack_type)

    print("正在加载输入数据集...")
    try:
        input_dataset = generator.load_dataset(args.input)
        print(f"成功加载 {len(input_dataset)} 个任务")
    except Exception as e:
        print(f"加载数据集失败: {e}")
        sys.exit(1)

    print("正在生成攻击工具数据集...")
    try:
        attack_dataset = generator.generate_attack_dataset(input_dataset)
        print("正在保存攻击工具数据集...")
        generator.save_dataset(attack_dataset, args.output)
        print("处理完成!")
    except Exception as e:
        print(f"生成攻击工具数据集失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()