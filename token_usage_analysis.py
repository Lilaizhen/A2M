#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析攻击情况下相对于baseline的token消耗倍数（多次运行平均值）
同时报告算术平均与几何平均
"""

import json
import os
import math

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
    计算多个文件的平均token使用情况（只统计success和agent_error的任务）
    返回：avg_prompt_tokens, avg_completion_tokens, avg_cost
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0
    valid_file_count = 0

    if len(file_list) == 0:
        return 0, 0, 0

    for filepath in file_list:
        data = load_json_file(filepath)
        # 只统计success和agent_error状态的任务
        valid_tasks = [task for task in data['task_details']
                      if task['completion_reason']['failure_type'] in ['success', 'agent_error']]

        if valid_tasks:
            # 计算有效任务的token使用总和
            prompt_tokens = sum(task['token_usage']['prompt_tokens'] for task in valid_tasks)
            completion_tokens = sum(task['token_usage']['completion_tokens'] for task in valid_tasks)
            cost = calculate_token_cost(prompt_tokens, completion_tokens)

            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            total_cost += cost
            valid_file_count += 1

    if valid_file_count == 0:
        return 0, 0, 0

    avg_prompt_tokens = total_prompt_tokens / valid_file_count
    avg_completion_tokens = total_completion_tokens / valid_file_count
    avg_cost = total_cost / valid_file_count

    return avg_prompt_tokens, avg_completion_tokens, avg_cost

def calculate_task_average_usage(file_list):
    """
    计算多个文件中各任务的平均token使用情况（只统计success和agent_error的任务）
    返回：task_id -> { input, avg_prompt_tokens, avg_completion_tokens, avg_cost, ... }
    """
    task_data = {}
    valid_file_count = 0

    if len(file_list) == 0:
        return task_data

    # 初始化任务数据结构（只包含有效任务）
    first_file_data = load_json_file(file_list[0])
    valid_first_tasks = [task for task in first_file_data['task_details']
                        if task['completion_reason']['failure_type'] in ['success', 'agent_error']]

    for task in valid_first_tasks:
        task_id = task['task_id']
        task_data[task_id] = {
            'input': task['input'],
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_cost': 0
        }

    # 累加所有文件的数据（只统计有效任务）
    for filepath in file_list:
        data = load_json_file(filepath)
        valid_tasks = [task for task in data['task_details']
                      if task['completion_reason']['failure_type'] in ['success', 'agent_error']]

        if not valid_tasks:
            continue

        task_map = {task['task_id']: task for task in valid_tasks}
        valid_file_count += 1

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
    if valid_file_count > 0:
        for task_id, task_info in task_data.items():
            task_info['avg_prompt_tokens'] = task_info['total_prompt_tokens'] / valid_file_count
            task_info['avg_completion_tokens'] = task_info['total_completion_tokens'] / valid_file_count
            task_info['avg_cost'] = task_info['total_cost'] / valid_file_count

    return task_data

def arithmetic_mean(values):
    """算术平均（忽略 None / NaN）"""
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)

def geometric_mean(values):
    """
    几何平均：exp(平均 log)
    仅对正数有意义；忽略非正或非数值项
    """
    positives = [v for v in values if isinstance(v, (int, float)) and v > 0 and math.isfinite(v)]
    if not positives:
        return 0.0
    log_sum = sum(math.log(v) for v in positives)
    return math.exp(log_sum / len(positives))

def analyze_token_usage(attack_files, baseline_files):
    """
    分析token使用情况并计算倍数（多次运行平均值）
    打印：总体成本比、逐任务倍数；给出逐任务倍数的算术平均与几何平均
    返回：(overall_multiplier, task_multipliers, amean, gmean)
    """
    # 计算攻击和baseline的平均值（汇总口径）
    attack_avg_prompt, attack_avg_completion, attack_avg_cost = calculate_average_usage(attack_files)
    baseline_avg_prompt, baseline_avg_completion, baseline_avg_cost = calculate_average_usage(baseline_files)

    overall_multiplier = attack_avg_cost / baseline_avg_cost if baseline_avg_cost > 0 else 0

    # 计算有效文件数量（用于显示）
    valid_attack_count = sum(1 for filepath in attack_files
                           if any(task['completion_reason']['failure_type'] in ['success', 'agent_error']
                                 for task in load_json_file(filepath)['task_details']))

    valid_baseline_count = sum(1 for filepath in baseline_files
                             if any(task['completion_reason']['failure_type'] in ['success', 'agent_error']
                                   for task in load_json_file(filepath)['task_details']))

    print(f"=== 总体Token消耗分析（{valid_attack_count}次攻击运行 和 {valid_baseline_count}次baseline运行 的平均） ===")
    print(f"Baseline平均总成本: {baseline_avg_cost:.0f}")
    print(f"攻击平均总成本: {attack_avg_cost:.0f}")
    print(f"总体倍数（汇总口径）: {overall_multiplier:.2f}x")
    print()

    # 逐任务分析
    print(f"=== 逐任务Token消耗分析（{valid_attack_count}次攻击运行 和 {valid_baseline_count}次baseline运行 的平均） ===")
    task_multipliers = []
    skipped = 0

    # 计算各任务的平均使用情况
    attack_task_data = calculate_task_average_usage(attack_files)
    baseline_task_data = calculate_task_average_usage(baseline_files)

    for task_id, attack_task_info in attack_task_data.items():
        task_name = attack_task_info['input'][:50] + "..."  # 截取前50个字符作为任务名称

        if task_id in baseline_task_data:
            baseline_task_info = baseline_task_data[task_id]

            # 获取平均成本
            attack_avg_cost_task = attack_task_info['avg_cost']
            baseline_avg_cost_task = baseline_task_info['avg_cost']

            # 计算倍数（仅当baseline>0）
            if baseline_avg_cost_task > 0:
                multiplier = attack_avg_cost_task / baseline_avg_cost_task
                task_multipliers.append(multiplier)

                print(f"任务: {task_name}")
                print(f"  Baseline平均成本: {baseline_avg_cost_task:.0f}")
                print(f"  攻击平均成本: {attack_avg_cost_task:.0f}")
                print(f"  倍数: {multiplier:.2f}x\n")
            else:
                skipped += 1
        else:
            skipped += 1

    # 聚合：算术平均 & 几何平均
    amean = arithmetic_mean(task_multipliers)
    gmean = geometric_mean(task_multipliers)

    if skipped > 0:
        print(f"注意：有 {skipped} 个任务因基线成本为0或缺失而被跳过。")

    if task_multipliers:
        print(f"=== 逐任务倍数的算术平均: {amean:.2f}x ===")
        print(f"=== 逐任务倍数的几何平均: {gmean:.2f}x ===")
    else:
        print("未得到有效的逐任务倍数，无法计算均值。")

    return overall_multiplier, task_multipliers, amean, gmean

if __name__ == "__main__":
    # 文件路径
    attack_files = [
        "/home/llz/myMCP-Bench/diverse/MCP-Bench/results/2025-10-02_22-59-47_moonshotai/Kimi-K2-Instruct-0905_test/results.json"
    ]
    baseline_files = [
        "/home/llz/myMCP-Bench/baseline/MCP-Bench/results/2025-10-02_23-05-45_moonshotai/Kimi-K2-Instruct-0905_test/results.json"
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
