#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP-Bench 攻击工具生成器
简化版本 - 单一脚本实现（已移除模拟执行器相关代码；变异=LLM新种子；路径健壮化）
"""

import argparse
import asyncio

from src.core.attack_generator_core import AttackGenerator, AttackType


async def main():
    parser = argparse.ArgumentParser(description="MCP-Bench 攻击工具生成器")
    parser.add_argument("input_dataset", help="输入数据集路径（JSON格式）")
    parser.add_argument("-o", "--output", default="results/attack_dataset.json", help="输出路径")
    parser.add_argument("--iterations", type=int, default=3, help="迭代轮数")
    parser.add_argument("--model", default="glm-4.5", help="LLM 模型")
    parser.add_argument("--api-key", help="API 密钥")
    parser.add_argument("--api-base", help="API 基础URL")
    parser.add_argument("--attack-type", choices=["resource_waste", "task_failure", "inappropriate_output"],
                        default="resource_waste", help="攻击类型")
    parser.add_argument("--cross-task", action="store_true", help="使用跨任务优化")
    parser.add_argument("--output-dir", help="迭代结果输出目录")

    args = parser.parse_args()

    # 确定攻击类型
    attack_type_map = {
        "resource_waste": AttackType.RESOURCE_WASTE,
        "task_failure": AttackType.TASK_FAILURE,
        "inappropriate_output": AttackType.INAPPROPRIATE_OUTPUT
    }
    attack_type = attack_type_map[args.attack_type]

    # 创建攻击生成器
    generator = AttackGenerator(
        api_key=args.api_key,
        api_base=args.api_base,
        attack_type=attack_type
    )

    # 加载数据集
    input_dataset = generator.load_dataset(args.input_dataset)

    # 生成攻击工具数据集
    if args.cross_task:
        attack_dataset = generator.generate_attack_dataset_cross_task(
            input_dataset, args.iterations, args.output_dir)
    else:
        attack_dataset = await generator.generate_attack_dataset(
            input_dataset, args.iterations, args.output_dir)

    # 保存结果
    generator.save_dataset(attack_dataset, args.output)

    print(f"\n攻击工具数据集生成完成！")
    print(f"输入数据集: {args.input_dataset}")
    print(f"输出路径: {args.output}")
    print(f"攻击类型: {args.attack_type}")
    print(f"迭代轮数: {args.iterations}")
    if args.cross_task:
        print("优化模式: 跨任务整体优化")
    else:
        print("优化模式: 单任务逐个优化")
    if args.output_dir:
        print(f"迭代输出目录: {args.output_dir}")


if __name__ == "__main__":
    asyncio.run(main())