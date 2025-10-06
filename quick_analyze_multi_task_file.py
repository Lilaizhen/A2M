#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速分析包含多个任务结果的文件脚本（不调用LLM）
"""

import json
import argparse
import os
from typing import Dict, List

def analyze_multi_task_results_quick(file_path: str) -> Dict:
    """
    快速分析包含多个任务结果的文件

    Args:
        file_path: 包含多个任务结果的文件路径

    Returns:
        统计信息
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"分析文件: {file_path}")

        # 获取任务详情列表
        task_details = data.get("task_details", [])
        overall_stats = data.get("overall_statistics", {})

        if not task_details:
            print(f"警告: 文件中未找到任务详情")
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "completion_rate": 0.0,
                "tool_calls": 0,
                "mytool_calls": 0,
                "details": []
            }

        print(f"开始分析 {len(task_details)} 个任务结果")

        total_tasks = len(task_details)
        completed_tasks = 0
        total_tool_calls = 0
        total_mytool_calls = 0
        details = []

        for i, task_detail in enumerate(task_details):
            task_id = task_detail.get("task_id", f"task_{i}")
            task_completed = task_detail.get("task_completed", False)
            tool_calls = task_detail.get("total_tool_calls", 0)
            mytool_calls = task_detail.get("mytool_calls", 0)

            if task_completed:
                completed_tasks += 1

            total_tool_calls += tool_calls
            total_mytool_calls += mytool_calls

            details.append({
                "task_id": task_id,
                "completed": task_completed,
                "tool_calls": tool_calls,
                "mytool_calls": mytool_calls
            })

        # 计算完成率
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": completion_rate,
            "total_tool_calls": total_tool_calls,
            "total_mytool_calls": total_mytool_calls,
            "overall_stats": overall_stats,
            "details": details
        }

    except Exception as e:
        return {
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(
        description='快速分析包含多个任务结果的文件（不调用LLM）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
使用示例:
  # 快速分析任务结果文件
  python quick_analyze_multi_task_file.py --result-file info_result.json
        '''
    )

    parser.add_argument('--result-file', type=str, required=True, help='包含多个任务结果的文件路径')

    args = parser.parse_args()

    if not os.path.exists(args.result_file):
        print(f"错误: 文件 {args.result_file} 不存在")
        return

    result = analyze_multi_task_results_quick(args.result_file)

    if "error" in result:
        print(f"分析出错: {result['error']}")
        return

    # 输出结果
    print("\n" + "="*60)
    print("任务结果分析统计")
    print("="*60)
    print(f"总任务数: {result['total_tasks']}")
    print(f"完成任务数: {result['completed_tasks']}")
    print(f"任务完成率: {result['completion_rate']:.2f}%")
    print(f"总工具调用次数: {result['total_tool_calls']}")
    print(f"恶意工具调用次数: {result['total_mytool_calls']}")

    # 显示详细信息（前15个）
    if result['details']:
        print("\n详细信息:")
        print("-" * 60)
        for i, detail in enumerate(result['details'][:15]):
            status = "完成" if detail['completed'] else "未完成"
            print(f"  {i+1:2d}. {detail['task_id']}: {status}, 工具调用 {detail['tool_calls']}, 恶意工具 {detail['mytool_calls']}")

        if len(result['details']) > 15:
            print(f"  ... 还有 {len(result['details']) - 15} 个任务")

if __name__ == "__main__":
    main()