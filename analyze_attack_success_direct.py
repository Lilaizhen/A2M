#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接使用原模块分析攻击成功率的脚本
"""

import json
import os
import argparse
from typing import Dict, List
from src.attacks.scoring.fitness_calculator import FitnessCalculator, AttackType

def load_run_details_from_files(result_dir: str) -> List[Dict]:
    """
    从攻击结果文件中提取run_detail信息

    Args:
        result_dir: 攻击结果文件目录

    Returns:
        run_detail字典列表
    """
    run_details = []

    # 遍历目录中的所有JSON文件
    for root, dirs, files in os.walk(result_dir):
        for file in files:
            if file.endswith('iteration_0.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 从攻击结果文件中提取run_detail信息
                    # 这里需要模拟run_detail的结构
                    run_detail = {
                        "status": "success",  # 假设任务成功完成
                        "action_trace": [],   # 实际应用中需要从攻击结果中提取
                        "token_usage": {},
                        "total_tool_calls": 0,
                        "mytool_calls": 0
                    }

                    run_details.append(run_detail)
                except Exception as e:
                    print(f"警告: 无法处理文件 {file_path}: {e}")

    return run_details

def analyze_attack_success_from_files(result_dir: str, api_key: str = None) -> Dict:
    """
    直接从攻击结果文件分析攻击成功率

    Args:
        result_dir: 攻击结果文件目录
        api_key: API密钥

    Returns:
        攻击成功率统计信息
    """
    # 初始化信息泄漏攻击的适应度计算器
    fitness_calculator = FitnessCalculator(AttackType.INFORMATION_LEAKAGE, api_key)

    # 遍历目录中的所有JSON文件
    total_files = 0
    success_count = 0

    print(f"开始分析 {result_dir} 目录中的攻击结果...")

    for root, dirs, files in os.walk(result_dir):
        for file in files:
            if file.endswith('iteration_0.json'):
                file_path = os.path.join(root, file)
                total_files += 1
                print(f"\n分析文件 {total_files}: {file_path}")

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 构造run_detail字典，符合FitnessCalculator的接口要求
                    # 从攻击结果中提取实际的行为轨迹
                    action_trace = []
                    if "task_details" in data and len(data["task_details"]) > 0:
                        # 如果是完整的攻击运行结果
                        action_trace = data["task_details"][0].get("action_trace", [])
                        task_completed = data["task_details"][0].get("task_completed", False)
                        token_usage = data["task_details"][0].get("token_usage", {})
                        total_tool_calls = data["task_details"][0].get("total_tool_calls", 0)
                        mytool_calls = data["task_details"][0].get("mytool_calls", 0)
                    else:
                        # 如果是任务迭代结果
                        # 从current_best或其他字段中提取信息
                        task_completed = True  # 假设任务完成
                        token_usage = {}
                        total_tool_calls = 0
                        mytool_calls = 0

                    run_detail = {
                        "status": "success" if task_completed else "failed",
                        "action_trace": action_trace,
                        "token_usage": token_usage,
                        "total_tool_calls": total_tool_calls,
                        "mytool_calls": mytool_calls
                    }

                    # 基线是否成功（这里假设为False，因为我们关注的是攻击效果）
                    baseline_ok = False

                    # 计算适应度分数（即攻击成功率）
                    score = fitness_calculator.score(run_detail, baseline_ok)

                    print(f"  危害分数: {score:.3f}")

                    # 判断攻击是否成功（分数大于0视为成功）
                    if score > 0:
                        success_count += 1
                        print(f"  攻击结果: 成功")
                    else:
                        print(f"  攻击结果: 失败")

                except Exception as e:
                    print(f"  分析出错: {e}")

    # 计算总体成功率
    success_rate = (success_count / total_files * 100) if total_files > 0 else 0

    return {
        "total_files": total_files,
        "success_count": success_count,
        "success_rate": success_rate
    }

def analyze_single_file(file_path: str, api_key: str = None) -> Dict:
    """
    分析单个攻击结果文件

    Args:
        file_path: 攻击结果文件路径
        api_key: API密钥

    Returns:
        分析结果
    """
    # 初始化信息泄漏攻击的适应度计算器
    fitness_calculator = FitnessCalculator(AttackType.INFORMATION_LEAKAGE, api_key)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"分析文件: {file_path}")

        # 构造run_detail字典
        action_trace = []
        if "task_details" in data and len(data["task_details"]) > 0:
            # 如果是完整的攻击运行结果
            action_trace = data["task_details"][0].get("action_trace", [])
            task_completed = data["task_details"][0].get("task_completed", False)
            token_usage = data["task_details"][0].get("token_usage", {})
            total_tool_calls = data["task_details"][0].get("total_tool_calls", 0)
            mytool_calls = data["task_details"][0].get("mytool_calls", 0)
        else:
            # 如果是任务迭代结果
            task_completed = True
            token_usage = {}
            total_tool_calls = 0
            mytool_calls = 0

        run_detail = {
            "status": "success" if task_completed else "failed",
            "action_trace": action_trace,
            "token_usage": token_usage,
            "total_tool_calls": total_tool_calls,
            "mytool_calls": mytool_calls
        }

        # 基线是否成功
        baseline_ok = False

        # 计算适应度分数
        score = fitness_calculator.score(run_detail, baseline_ok)

        return {
            "harm_score": score,
            "task_completed": task_completed,
            "total_tool_calls": total_tool_calls,
            "mytool_calls": mytool_calls,
            "token_usage": token_usage
        }

    except Exception as e:
        return {
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description='直接使用原模块分析攻击成功率')
    parser.add_argument('--result-dir', type=str, help='攻击结果目录路径')
    parser.add_argument('--result-file', type=str, help='单个攻击结果文件路径')
    parser.add_argument('--api-key', type=str, default=None, help='API密钥（可选）')

    args = parser.parse_args()

    if args.result_dir:
        # 分析目录中的所有结果文件
        if not os.path.exists(args.result_dir):
            print(f"错误: 目录 {args.result_dir} 不存在")
            return

        stats = analyze_attack_success_from_files(args.result_dir, args.api_key)

        # 输出结果
        print("\n==================== 攻击成功率分析结果 ====================")
        print(f"总文件数: {stats['total_files']}")
        print(f"攻击成功数: {stats['success_count']}")
        print(f"攻击成功率: {stats['success_rate']:.2f}%")

    elif args.result_file:
        # 分析单个结果文件
        if not os.path.exists(args.result_file):
            print(f"错误: 文件 {args.result_file} 不存在")
            return

        result = analyze_single_file(args.result_file, args.api_key)

        if "error" in result:
            print(f"分析出错: {result['error']}")
            return

        # 输出结果
        print("\n==================== 分析结果 ====================")
        print(f"危害分数: {result['harm_score']:.3f}")
        print(f"任务完成: {'是' if result['task_completed'] else '否'}")
        print(f"总工具调用次数: {result['total_tool_calls']}")
        print(f"恶意工具调用次数: {result['mytool_calls']}")
        print(f"Token使用情况: {result['token_usage']}")

        if result['harm_score'] > 0:
            print("\n攻击结果: 成功")
        else:
            print("\n攻击结果: 失败")

    else:
        print("请指定 --result-dir 或 --result-file 参数")
        return

if __name__ == "__main__":
    main()