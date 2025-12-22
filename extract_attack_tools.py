#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取攻击工具脚本 - 从结果文件夹中提取攻击工具，生成标准攻击数据集格式
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict


def extract_attack_tools_from_results(base_dir: str, scenario_filter: str = None) -> List[Dict]:
    """从结果文件夹中提取攻击工具"""
    attack_tools = []
    base_path = Path(base_dir)

    if not base_path.exists():
        print(f"错误: 基础目录不存在: {base_dir}")
        return attack_tools

    # 遍历所有结果文件夹
    for folder in base_path.iterdir():
        if not folder.is_dir():
            continue

        # 应用场景过滤器
        if scenario_filter and scenario_filter not in folder.name:
            continue

        print(f"处理文件夹: {folder.name}")

        # 遍历所有任务子目录
        for task_dir in folder.iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
                continue

            task_id = task_dir.name
            best_tool = None
            best_score = -1

            # 获取该任务的所有iteration文件
            iteration_files = sorted(task_dir.glob("iteration_*.json"))

            for iter_file in iteration_files:
                try:
                    with open(iter_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 获取当前最佳工具
                    current_best = data.get("current_best", {})
                    if current_best and "tool" in current_best:
                        tool_data = current_best["tool"]
                        score = current_best.get("score", 0)
                        mytool_calls = current_best.get("mytool_calls", 0)

                        # 只保存有工具调用的结果，且分数更高
                        if mytool_calls > 0 and score > best_score:
                            best_tool = tool_data
                            best_score = score
                except Exception as e:
                    print(f"警告: 处理文件 {iter_file} 失败: {e}")
                    continue

            # 如果找到了最佳工具，添加到结果中
            if best_tool:
                attack_tools.append({
                    "task_id": task_id,
                    "attack_tools": [best_tool],
                    "final_score": best_score
                })

    return attack_tools


def main():
    parser = argparse.ArgumentParser(
        description="提取攻击工具脚本 - 从结果文件夹中提取攻击工具，生成标准攻击数据集格式"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="./results_attack",
        help="结果文件夹的基础目录 (默认: ./results_attack)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./attack_tools_extracted.json",
        help="输出JSON文件路径 (默认: ./attack_tools_extracted.json)"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"],
        help="只提取指定攻击场景的工具"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0,
        help="只提取分数大于等于此值的工具 (默认: 0)"
    )

    args = parser.parse_args()

    print(f"开始提取攻击工具 from: {args.base_dir}")

    # 提取攻击工具
    attack_tools = extract_attack_tools_from_results(args.base_dir, args.scenario)

    # 应用分数过滤器
    if args.min_score > 0:
        attack_tools = [tool for tool in attack_tools if tool.get("final_score", 0) >= args.min_score]

    if not attack_tools:
        print("没有找到符合条件的攻击工具")
        return

    # 保存结果
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(attack_tools, f, indent=2, ensure_ascii=False)

    # 计算统计信息
    total_tools = len(attack_tools)
    avg_score = sum(tool.get("final_score", 0) for tool in attack_tools) / total_tools
    max_score = max(tool.get("final_score", 0) for tool in attack_tools)
    min_score = min(tool.get("final_score", 0) for tool in attack_tools)

    score_ge_2 = sum(1 for tool in attack_tools if tool.get("final_score", 0) >= 2)
    score_eq_4 = sum(1 for tool in attack_tools if tool.get("final_score", 0) == 4)

    print(f"\n提取完成！")
    print(f"📊 共提取 {total_tools} 个攻击工具")
    print(f"📊 平均分数: {avg_score:.2f}")
    print(f"📊 最高分数: {max_score:.2f}")
    print(f"📊 最低分数: {min_score:.2f}")
    print(f"📈 分数≥2: {score_ge_2}个 ({score_ge_2/total_tools*100:.1f}%)")
    print(f"⭐ 分数=4: {score_eq_4}个 ({score_eq_4/total_tools*100:.1f}%)")
    print(f"📄 结果保存到: {args.output}")


if __name__ == "__main__":
    main()