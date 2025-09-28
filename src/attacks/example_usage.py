#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块化攻击生成器使用示例
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入模块化攻击生成器
from src.attacks import AttackGenerator, AttackType

def main():
    """演示如何使用模块化的攻击生成器"""
    print("=== MCP-Bench 模块化攻击生成器使用示例 ===")

    # 创建资源浪费类型的攻击生成器
    print("\n1. 创建资源浪费攻击生成器...")
    resource_waste_generator = AttackGenerator(attack_type=AttackType.RESOURCE_WASTE)
    print("   成功创建资源浪费攻击生成器")

    # 创建任务失败类型的攻击生成器
    print("\n2. 创建任务失败攻击生成器...")
    task_failure_generator = AttackGenerator(attack_type=AttackType.TASK_FAILURE)
    print("   成功创建任务失败攻击生成器")

    # 创建信息泄漏类型的攻击生成器
    print("\n3. 创建信息泄漏攻击生成器...")
    information_leakage_generator = AttackGenerator(attack_type=AttackType.INFORMATION_LEAKAGE)
    print("   成功创建信息泄漏攻击生成器")

    # 示例任务数据
    sample_task = {
        "id": "task-001",
        "description": "分析用户提供的文档并提取关键信息",
        "input": "请分析这份技术文档并总结主要观点",
        "expected_tools": ["document_analyzer", "summarizer"]
    }

    # 为不同攻击场景生成攻击工具示例
    print("\n4. 生成不同攻击场景的攻击工具...")

    try:
        print("   生成资源浪费攻击工具...")
        resource_tool = resource_waste_generator.generate_attack_tool(sample_task)
        print(f"   成功生成资源浪费攻击工具: {resource_tool['attack_tools'][0]['name']}")

        print("   生成任务失败攻击工具...")
        failure_tool = task_failure_generator.generate_attack_tool(sample_task)
        print(f"   成功生成任务失败攻击工具: {failure_tool['attack_tools'][0]['name']}")

        print("   生成信息泄漏攻击工具...")
        information_leakage_tool = information_leakage_generator.generate_attack_tool(sample_task)
        print(f"   成功生成信息泄漏攻击工具: {information_leakage_tool['attack_tools'][0]['name']}")

    except Exception as e:
        print(f"   生成攻击工具时出错: {e}")

    print("\n=== 模块化结构优势 ===")
    print("1. 每个攻击场景独立实现，便于维护和扩展")
    print("2. 适应度计算独立封装，可按需替换")
    print("3. 核心执行逻辑与场景生成逻辑分离")
    print("4. 代码结构清晰，易于理解和修改")

    print("\n=== 使用建议 ===")
    print("1. 根据具体需求选择合适的攻击类型")
    print("2. 可通过继承和重写方法来自定义特定行为")
    print("3. 利用模块化结构可以轻松添加新的攻击场景")

if __name__ == "__main__":
    main()