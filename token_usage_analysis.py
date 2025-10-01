#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析攻击情况下相对于baseline的token消耗倍数（多次运行平均值）
"""

import json
import os

def calculate_token_cost(prompt_tokens, completion_tokens):
    """
    计算token消耗成本
    根据要求：completion_tokens的数量*5 加上 prompt_tokens 的数量
    """
    return completion_tokens * 5 + prompt_tokens

def load_json_file(filepath):
    """
    加载JSON文件
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_average_usage(file_list):
    """
    计算多个文件的平均token使用情况
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0
    file_count = len(file_list)

    if file_count == 0:
        return 0, 0, 0

    for filepath in file_list:
        data = load_json_file(filepath)
        token_usage = data['overall_statistics']['token_usage']
        prompt_tokens = token_usage['prompt_tokens']
        completion_tokens = token_usage['completion_tokens']
        cost = calculate_token_cost(prompt_tokens, completion_tokens)

        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += cost

    avg_prompt_tokens = total_prompt_tokens / file_count
    avg_completion_tokens = total_completion_tokens / file_count
    avg_cost = total_cost / file_count

    return avg_prompt_tokens, avg_completion_tokens, avg_cost

def calculate_task_average_usage(file_list):
    """
    计算多个文件中各任务的平均token使用情况
    """
    task_data = {}
    file_count = len(file_list)

    if file_count == 0:
        return task_data

    # 初始化任务数据结构
    first_file_data = load_json_file(file_list[0])
    for task in first_file_data['task_details']:
        task_id = task['task_id']
        task_data[task_id] = {
            'input': task['input'],
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_cost': 0
        }

    # 累加所有文件的数据
    for filepath in file_list:
        data = load_json_file(filepath)
        task_map = {task['task_id']: task for task in data['task_details']}

        for task_id, task_info in task_data.items():
            if task_id in task_map:
                task_tokens = task_map[task_id]['token_usage']
                prompt_tokens = task_tokens['prompt_tokens']
                completion_tokens = task_tokens['completion_tokens']
                cost = calculate_token_cost(prompt_tokens, completion_tokens)

                task_info['total_prompt_tokens'] += prompt_tokens
                task_info['total_completion_tokens'] += completion_tokens
                task_info['total_cost'] += cost

    # 计算平均值
    for task_id, task_info in task_data.items():
        task_info['avg_prompt_tokens'] = task_info['total_prompt_tokens'] / file_count
        task_info['avg_completion_tokens'] = task_info['total_completion_tokens'] / file_count
        task_info['avg_cost'] = task_info['total_cost'] / file_count

    return task_data

def analyze_token_usage(attack_files, baseline_files):
    """
    分析token使用情况并计算倍数（多次运行平均值）
    """
    # 计算攻击和baseline的平均值
    attack_avg_prompt, attack_avg_completion, attack_avg_cost = calculate_average_usage(attack_files)
    baseline_avg_prompt, baseline_avg_completion, baseline_avg_cost = calculate_average_usage(baseline_files)

    overall_multiplier = attack_avg_cost / baseline_avg_cost if baseline_avg_cost > 0 else 0

    print(f"=== 总体Token消耗分析（{len(attack_files)}次攻击运行和{len(baseline_files)}次baseline运行平均值） ===")
    print(f"Baseline平均总成本: {baseline_avg_cost:.0f}")
    print(f"攻击平均总成本: {attack_avg_cost:.0f}")
    print(f"总体倍数: {overall_multiplier:.2f}x")
    print()

    # 逐任务分析
    print(f"=== 逐任务Token消耗分析（{len(attack_files)}次攻击运行和{len(baseline_files)}次baseline运行平均值） ===")
    task_multipliers = []

    # 计算各任务的平均使用情况
    attack_task_data = calculate_task_average_usage(attack_files)
    baseline_task_data = calculate_task_average_usage(baseline_files)

    for task_id, attack_task_info in attack_task_data.items():
        task_name = attack_task_info['input'][:50] + "..."  # 截取前50个字符作为任务名称

        if task_id in baseline_task_data:
            baseline_task_info = baseline_task_data[task_id]

            # 获取平均成本
            attack_avg_cost = attack_task_info['avg_cost']
            baseline_avg_cost = baseline_task_info['avg_cost']

            # 计算倍数
            multiplier = attack_avg_cost / baseline_avg_cost if baseline_avg_cost > 0 else 0
            task_multipliers.append(multiplier)

            print(f"任务: {task_name}")
            print(f"  Baseline平均成本: {baseline_avg_cost:.0f}")
            print(f"  攻击平均成本: {attack_avg_cost:.0f}")
            print(f"  倍数: {multiplier:.2f}x")
            print()

    # 计算平均倍数
    if task_multipliers:
        average_multiplier = sum(task_multipliers) / len(task_multipliers)
        print(f"=== 平均倍数: {average_multiplier:.2f}x ===")

    return overall_multiplier, task_multipliers

if __name__ == "__main__":
    # 文件路径
    attack_files = [

        "/home/llz/MCP-Bench/results/2025-10-02_00-26-35_moonshotai/Kimi-K2-Instruct-0905_test/results.json"
    ]
    baseline_files = [
        "/home/llz/myMCP-Bench/baseline/MCP-Bench/results/2025-10-01_15-51-37_moonshotai/Kimi-K2-Instruct-0905_test/results.json"
    ]

    # 检查文件是否存在
    all_files = attack_files + baseline_files
    missing_files = [f for f in all_files if not os.path.exists(f)]

    if missing_files:
        print(f"错误: 以下文件不存在:")
        for f in missing_files:
            print(f"  {f}")
        exit(1)

    # 分析token使用情况
    analyze_token_usage(attack_files, baseline_files)