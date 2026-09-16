#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取攻击工具脚本 - 支持从单个指定文件夹或批量从结果目录中提取
(已修改: 去除 task_id 中的 'task_' 前缀)
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict


def process_single_result_folder(folder_path: Path) -> List[Dict]:
    """
    处理单个结果文件夹的核心逻辑
    :param folder_path: 包含 task_ 子目录的具体结果文件夹路径
    :return: 提取出的工具列表
    """
    folder_tools = []
    
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"警告: 路径不存在或不是文件夹: {folder_path}")
        return folder_tools

    print(f"正在处理文件夹: {folder_path.name}")

    # 遍历所有任务子目录 (task_*)
    for task_dir in folder_path.iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue

        # 【修改处】: 去掉 task_ 前缀
        # 例如: "task_10" -> "10"
        task_id = task_dir.name.replace("task_", "")
        
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
                    if  score > best_score:
                        best_tool = tool_data
                        best_score = score
            except Exception as e:
                print(f"警告: 处理文件 {iter_file} 失败: {e}")
                continue

        # 如果找到了最佳工具，添加到结果中
        if best_tool:
            folder_tools.append({
                "source_folder": folder_path.name,
                "task_id": task_id,  # 这里现在存储的是没有前缀的ID
                "attack_tools": [best_tool],
                "final_score": best_score
            })
            
    return folder_tools


def extract_attack_tools(base_dir: str = None, target_path: str = None, scenario_filter: str = None) -> List[Dict]:
    """
    提取攻击工具的主控函数
    """
    all_attack_tools = []

    # 模式 1: 指定了具体的单个目标文件夹
    if target_path:
        path = Path(target_path)
        all_attack_tools.extend(process_single_result_folder(path))
    
    # 模式 2: 指定了基础目录，遍历其下所有子文件夹
    elif base_dir:
        base_path = Path(base_dir)
        if not base_path.exists():
            print(f"错误: 基础目录不存在: {base_dir}")
            return []

        # 遍历所有结果文件夹
        for folder in base_path.iterdir():
            if not folder.is_dir():
                continue

            # 应用场景过滤器
            if scenario_filter and scenario_filter not in folder.name:
                continue

            # 调用处理单个文件夹的逻辑
            all_attack_tools.extend(process_single_result_folder(folder))
    
    else:
        print("错误: 必须指定 --base-dir 或 --target-path")

    return all_attack_tools


def main():
    parser = argparse.ArgumentParser(
        description="提取攻击工具脚本 - 从结果文件夹中提取攻击工具"
    )
    
    # 两个互斥的路径参数
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--base-dir",
        type=str,
        help="【批量模式】结果文件夹的基础目录 (例如: ./results_attack)"
    )
    group.add_argument(
        "--target-path",
        type=str,
        help="【单文件夹模式】指定具体的某个结果文件夹路径 (例如: ./results_attack/resource_waste_run1)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./attack_tools_extracted.json",
        help="输出JSON文件路径"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"],
        help="只提取指定攻击场景的工具 (仅在使用 --base-dir 时有效)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0,
        help="只提取分数大于等于此值的工具 (默认: 4)"
    )

    args = parser.parse_args()

    if args.target_path:
        print(f"开始从指定文件夹提取: {args.target_path}")
    else:
        print(f"开始从基础目录扫描: {args.base_dir}")

    # 提取攻击工具
    attack_tools = extract_attack_tools(
        base_dir=args.base_dir, 
        target_path=args.target_path,
        scenario_filter=args.scenario
    )

    # 应用分数过滤器
    if args.min_score > 0:
        original_count = len(attack_tools)
        attack_tools = [tool for tool in attack_tools if tool.get("final_score", 0) >= args.min_score]
        if len(attack_tools) < original_count:
            print(f"过滤: 移除了 {original_count - len(attack_tools)} 个分数低于 {args.min_score} 的工具")

    if not attack_tools:
        print("❌ 没有找到符合条件的攻击工具")
        return

    # 保存结果
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(attack_tools, f, indent=2, ensure_ascii=False)

    # 计算统计信息
    total_tools = len(attack_tools)
    avg_score = sum(tool.get("final_score", 0) for tool in attack_tools) / total_tools if total_tools > 0 else 0
    max_score = max(tool.get("final_score", 0) for tool in attack_tools) if total_tools > 0 else 0
    min_score = min(tool.get("final_score", 0) for tool in attack_tools) if total_tools > 0 else 0

    score_ge_2 = sum(1 for tool in attack_tools if tool.get("final_score", 0) >= 2)
    score_eq_4 = sum(1 for tool in attack_tools if tool.get("final_score", 0) == 4)

    print(f"\n✅ 提取完成！")
    print(f"📊 共提取 {total_tools} 个攻击工具")
    print(f"📊 平均分数: {avg_score:.2f}")
    print(f"📊 最高分数: {max_score:.2f}")
    print(f"📊 最低分数: {min_score:.2f}")
    if total_tools > 0:
        print(f"📈 分数≥2: {score_ge_2}个 ({score_ge_2/total_tools*100:.1f}%)")
        print(f"⭐ 分数=4: {score_eq_4}个 ({score_eq_4/total_tools*100:.1f}%)")
    print(f"📄 结果保存到: {args.output}")


if __name__ == "__main__":
    main()