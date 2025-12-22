#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总攻击结果脚本
扫描结果文件夹，提取每个任务的最佳攻击工具，生成攻击数据集格式的汇总JSON
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


def scan_result_folders(base_dir: str) -> List[str]:
    """扫描结果文件夹，返回包含iteration_*.json文件的文件夹列表"""
    result_folders = []
    base_path = Path(base_dir)

    if not base_path.exists():
        print(f"错误: 基础目录不存在: {base_dir}")
        return result_folders

    # 遍历所有子目录
    for item in base_path.iterdir():
        if item.is_dir():
            # 检查是否包含任务子目录
            has_iterations = False
            for sub_item in item.iterdir():
                if sub_item.is_dir():
                    # 检查任务子目录中是否包含iteration_*.json文件
                    json_files = list(sub_item.glob("iteration_*.json"))
                    if json_files:
                        has_iterations = True
                        break
            if has_iterations:
                result_folders.append(str(item))

    return sorted(result_folders)


def extract_best_tools_from_folder(folder_path: str) -> List[Dict]:
    """从单个结果文件夹中提取每个任务的最佳攻击工具"""
    folder = Path(folder_path)
    task_results = {}

    # 遍历所有任务子目录
    for task_dir in folder.iterdir():
        if task_dir.is_dir():
            task_id = task_dir.name
            if not task_id.startswith("task_"):
                continue

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

                        # 只保存有工具调用的结果
                        if mytool_calls > 0:
                            # 如果已有结果，比较分数
                            if task_id not in task_results or score > task_results[task_id]["score"]:
                                task_results[task_id] = {
                                    "tool": tool_data,
                                    "score": score,
                                    "mytool_calls": mytool_calls,
                                    "iteration": int(iter_file.stem.split('_')[1]) if '_' in iter_file.stem else 0
                                }
                except Exception as e:
                    print(f"警告: 处理文件 {iter_file} 失败: {e}")
                    continue

    # 转换为列表格式
    best_tools = []
    for task_id, result in task_results.items():
        best_tools.append({
            "task_id": task_id,
            "attack_tools": [result["tool"]],
            "final_score": result["score"],
            "mytool_calls": result["mytool_calls"],
            "best_iteration": result["iteration"]
        })

    return best_tools


def extract_attack_scenario_from_folder(folder_path: str) -> str:
    """从文件夹路径中提取攻击场景名称"""
    folder_name = Path(folder_path).name

    # 常见的攻击场景关键词
    scenarios = ["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"]

    for scenario in scenarios:
        if scenario in folder_name:
            return scenario

    # 如果没有找到明确的场景，返回unknown
    return "unknown"


def create_summary_json(result_folders: List[str], output_file: str) -> None:
    """创建汇总JSON文件"""
    all_results = []
    summary_stats = {
        "total_tasks": 0,
        "total_folders": len(result_folders),
        "scenarios": {},
        "score_distribution": {
            "total_scores": 0,
            "avg_score": 0,
            "max_score": 0,
            "min_score": float('inf'),
            "score_ge_2_count": 0,
            "score_eq_4_count": 0
        }
    }

    all_scores = []

    for folder in result_folders:
        print(f"处理文件夹: {folder}")
        scenario = extract_attack_scenario_from_folder(folder)
        best_tools = extract_best_tools_from_folder(folder)

        if best_tools:
            # 添加到总结果
            all_results.extend(best_tools)

            # 更新统计
            summary_stats["total_tasks"] += len(best_tools)

            if scenario not in summary_stats["scenarios"]:
                summary_stats["scenarios"][scenario] = {
                    "count": 0,
                    "avg_score": 0,
                    "scores": []
                }

            summary_stats["scenarios"][scenario]["count"] += len(best_tools)

            # 收集分数用于统计
            for tool_data in best_tools:
                score = tool_data.get("final_score", 0)
                all_scores.append(score)
                summary_stats["scenarios"][scenario]["scores"].append(score)

                # 更新全局统计
                summary_stats["score_distribution"]["total_scores"] += 1
                summary_stats["score_distribution"]["max_score"] = max(summary_stats["score_distribution"]["max_score"], score)
                summary_stats["score_distribution"]["min_score"] = min(summary_stats["score_distribution"]["min_score"], score)

                if score >= 2:
                    summary_stats["score_distribution"]["score_ge_2_count"] += 1
                if score == 4:
                    summary_stats["score_distribution"]["score_eq_4_count"] += 1

    # 计算平均分
    if all_scores:
        summary_stats["score_distribution"]["avg_score"] = sum(all_scores) / len(all_scores)
        summary_stats["score_distribution"]["min_score"] = summary_stats["score_distribution"]["min_score"] if summary_stats["score_distribution"]["min_score"] != float('inf') else 0

        # 计算每个场景的平均分
        for scenario in summary_stats["scenarios"]:
            if summary_stats["scenarios"][scenario]["scores"]:
                summary_stats["scenarios"][scenario]["avg_score"] = sum(summary_stats["scenarios"][scenario]["scores"]) / len(summary_stats["scenarios"][scenario]["scores"])
    else:
        summary_stats["score_distribution"]["min_score"] = 0

    # 创建最终汇总
    final_summary = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "base_directory": os.path.dirname(result_folders[0]) if result_folders else "",
            "total_folders_processed": len(result_folders)
        },
        "summary_statistics": summary_stats,
        "attack_tools": all_results
    }

    # 保存到文件
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_summary, f, indent=2, ensure_ascii=False)

    print(f"\n汇总完成！")
    print(f"📊 处理了 {len(result_folders)} 个结果文件夹")
    print(f"📊 汇总了 {summary_stats['total_tasks']} 个任务")
    print(f"📊 平均攻击得分: {summary_stats['score_distribution']['avg_score']:.2f}")
    print(f"📊 评分≥2的任务: {summary_stats['score_distribution']['score_ge_2_count']}个 ({(summary_stats['score_distribution']['score_ge_2_count']/summary_stats['total_tasks']*100):.1f}%)")
    print(f"📊 评分=4的任务: {summary_stats['score_distribution']['score_eq_4_count']}个 ({(summary_stats['score_distribution']['score_eq_4_count']/summary_stats['total_tasks']*100):.1f}%)")
    print(f"📄 结果保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="汇总攻击结果脚本 - 扫描结果文件夹并生成攻击数据集格式的汇总JSON"
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
        default="./attack_summary.json",
        help="输出JSON文件路径 (默认: ./attack_summary.json)"
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="只处理包含指定字符串的文件夹名称"
    )

    args = parser.parse_args()

    print(f"开始扫描结果文件夹: {args.base_dir}")

    # 扫描结果文件夹
    result_folders = scan_result_folders(args.base_dir)

    if args.filter:
        result_folders = [f for f in result_folders if args.filter in f]
        print(f"应用过滤器 '{args.filter}' 后，剩余 {len(result_folders)} 个文件夹")

    if not result_folders:
        print("没有找到包含iteration文件的结果文件夹")
        return

    # 创建汇总JSON
    create_summary_json(result_folders, args.output)


if __name__ == "__main__":
    main()