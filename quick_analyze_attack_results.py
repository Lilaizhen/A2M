#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速分析多个攻击结果文件的脚本（不调用LLM）
"""

import json
import os
import argparse
from typing import Dict, List

def load_attack_results(result_dir: str) -> List[Dict]:
    """
    从攻击结果文件中加载数据

    Args:
        result_dir: 攻击结果文件目录

    Returns:
        攻击结果列表
    """
    results = []

    # 遍历目录中的所有JSON文件
    for root, _, files in os.walk(result_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 添加文件路径信息
                        data['file_path'] = file_path
                        results.append(data)
                except Exception as e:
                    print(f"警告: 无法加载文件 {file_path}: {e}")

    return results

def extract_basic_info_from_result(data: Dict) -> Dict:
    """
    从攻击结果数据中提取基本信息

    Args:
        data: 攻击结果数据

    Returns:
        基本信息字典
    """
    info = {
        "task_id": data.get("task_id", "unknown"),
        "current_best_score": 0.0,
        "tool_name": "",
        "tool_description": "",
        "total_tools": 0
    }

    try:
        # 尝试从不同格式的攻击结果中提取信息
        if "current_best" in data:
            current_best = data["current_best"]
            info["current_best_score"] = current_best.get("score", 0.0)
            if "tool" in current_best:
                tool = current_best["tool"]
                info["tool_name"] = tool.get("name", "")
                info["tool_description"] = tool.get("description", "")

        if "collection_stats" in data:
            info["total_tools"] = data["collection_stats"].get("total_tools", 0)

    except Exception as e:
        print(f"警告: 提取基本信息时出错: {e}")

    return info

def analyze_attack_results(result_dir: str) -> Dict:
    """
    分析攻击结果文件

    Args:
        result_dir: 攻击结果目录路径

    Returns:
        分析统计信息
    """
    # 加载攻击结果
    results = load_attack_results(result_dir)

    if not results:
        print(f"警告: 在目录 {result_dir} 中未找到攻击结果文件")
        return {
            "total_files": 0,
            "scores": [],
            "details": []
        }

    print(f"开始分析 {len(results)} 个攻击结果文件")

    scores = []
    details = []

    for i, result in enumerate(results):
        file_path = result.get('file_path', f'file_{i}')
        print(f"\n分析文件 ({i+1}/{len(results)}): {os.path.basename(file_path)}")

        try:
            # 提取基本信息
            info = extract_basic_info_from_result(result)

            score = info["current_best_score"]
            scores.append(score)

            print(f"  任务ID: {info['task_id']}")
            print(f"  适应度分数: {score:.3f}")
            print(f"  工具名称: {info['tool_name']}")
            print(f"  总工具数: {info['total_tools']}")

            details.append({
                "file": os.path.basename(file_path),
                "task_id": info["task_id"],
                "score": score,
                "tool_name": info["tool_name"],
                "total_tools": info["total_tools"]
            })

        except Exception as e:
            print(f"  分析出错: {e}")
            details.append({
                "file": os.path.basename(file_path),
                "task_id": "error",
                "score": 0.0,
                "tool_name": "",
                "total_tools": 0,
                "error": str(e)
            })

    return {
        "total_files": len(results),
        "scores": scores,
        "details": details
    }

def analyze_single_file(file_path: str) -> Dict:
    """
    分析单个攻击结果文件

    Args:
        file_path: 攻击结果文件路径

    Returns:
        分析结果
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"分析文件: {file_path}")

        # 提取基本信息
        info = extract_basic_info_from_result(data)

        return {
            "task_id": info["task_id"],
            "score": info["current_best_score"],
            "tool_name": info["tool_name"],
            "tool_description": info["tool_description"],
            "total_tools": info["total_tools"]
        }

    except Exception as e:
        return {
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(
        description='快速分析多个攻击结果文件的工具（不调用LLM）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
使用示例:
  # 分析目录中的所有攻击结果文件
  python quick_analyze_attack_results.py --result-dir datasets/attack_our/infomation/attack10

  # 分析单个攻击结果文件
  python quick_analyze_attack_results.py --result-file datasets/attack_our/infomation/attack10/task_xxx/iteration_0.json
        '''
    )

    parser.add_argument('--result-dir', type=str, help='攻击结果目录路径')
    parser.add_argument('--result-file', type=str, help='单个攻击结果文件路径')

    args = parser.parse_args()

    if args.result_dir:
        # 分析目录中的所有结果文件
        if not os.path.exists(args.result_dir):
            print(f"错误: 目录 {args.result_dir} 不存在")
            return

        stats = analyze_attack_results(args.result_dir)

        # 输出结果
        print("\n" + "="*60)
        print("攻击结果分析统计")
        print("="*60)
        print(f"总文件数: {stats['total_files']}")

        if stats['scores']:
            avg_score = sum(stats['scores']) / len(stats['scores'])
            max_score = max(stats['scores'])
            min_score = min(stats['scores'])
            print(f"平均分数: {avg_score:.3f}")
            print(f"最高分数: {max_score:.3f}")
            print(f"最低分数: {min_score:.3f}")

        # 成功率统计（假设分数>0为成功）
        success_count = sum(1 for score in stats['scores'] if score > 0)
        success_rate = (success_count / len(stats['scores']) * 100) if stats['scores'] else 0
        print(f"成功数量: {success_count}")
        print(f"成功率: {success_rate:.2f}%")

        # 显示详细信息（前15个）
        if stats['details']:
            print("\n详细信息:")
            print("-" * 60)
            for i, detail in enumerate(stats['details'][:15]):
                if 'error' in detail:
                    print(f"  {i+1:2d}. {detail['file']}: 错误 - {detail['error']}")
                else:
                    print(f"  {i+1:2d}. {detail['file']}: 分数 {detail['score']:.3f}, 工具 {detail['tool_name']}")

            if len(stats['details']) > 15:
                print(f"  ... 还有 {len(stats['details']) - 15} 个文件")

    elif args.result_file:
        # 分析单个结果文件
        if not os.path.exists(args.result_file):
            print(f"错误: 文件 {args.result_file} 不存在")
            return

        result = analyze_single_file(args.result_file)

        if "error" in result:
            print(f"分析出错: {result['error']}")
            return

        # 输出结果
        print("\n" + "="*60)
        print("攻击结果分析")
        print("="*60)
        print(f"任务ID: {result['task_id']}")
        print(f"适应度分数: {result['score']:.3f}")
        print(f"工具名称: {result['tool_name']}")
        print(f"总工具数: {result['total_tools']}")
        if result['tool_description']:
            print(f"工具描述: {result['tool_description'][:100]}...")

    else:
        print("请指定 --result-dir 或 --result-file 参数")
        parser.print_help()
        return

if __name__ == "__main__":
    main()