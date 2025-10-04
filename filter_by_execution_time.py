#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

def filter_tasks_by_execution_time():
    """
    根据result.json中的执行时间过滤任务
    """

    # 读取result.json文件
    result_file = "/home/llz/MCP-Bench/datasets/result.json"
    with open(result_file, 'r', encoding='utf-8') as f:
        result_data = json.load(f)

    # 读取all_annotations_filtered_short.json文件
    annotations_file = "/home/llz/MCP-Bench/datasets/all_annotations_filtered_short.json"
    with open(annotations_file, 'r', encoding='utf-8') as f:
        annotations_data = json.load(f)

    # 获取执行时间大于200秒的任务ID
    slow_task_ids = set()
    for task_detail in result_data.get('task_details', []):
        execution_time = task_detail.get('execution_time_seconds', 0)
        task_id = task_detail.get('task_id', '')
        if execution_time > 200:
            slow_task_ids.add(task_id)

    print(f"发现 {len(slow_task_ids)} 个执行时间超过200秒的任务:")
    for task_id in slow_task_ids:
        # 找到对应任务的执行时间
        for task_detail in result_data.get('task_details', []):
            if task_detail.get('task_id', '') == task_id:
                execution_time = task_detail.get('execution_time_seconds', 0)
                print(f"  - {task_id}: {execution_time:.2f} 秒")
                break

    print(f"\n过滤前共有 {len(annotations_data)} 个任务")

    # 过滤掉执行时间大于200秒的任务
    filtered_annotations = []
    for task in annotations_data:
        task_id = task.get('task_id', '')
        if task_id not in slow_task_ids:
            filtered_annotations.append(task)

    print(f"过滤后剩余 {len(filtered_annotations)} 个任务")
    print(f"移除了 {len(annotations_data) - len(filtered_annotations)} 个任务")

    # 保存过滤后的数据到新文件
    output_file = "/home/llz/MCP-Bench/datasets/all_annotations_filtered_short_time_filtered.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_annotations, f, ensure_ascii=False, indent=2)

    # 打印统计信息
    print(f"\n统计信息:")
    print(f"原始任务数: {len(annotations_data)}")
    print(f"移除任务数: {len(annotations_data) - len(filtered_annotations)}")
    print(f"剩余任务数: {len(filtered_annotations)}")
    print(f"过滤比例: {((len(annotations_data) - len(filtered_annotations)) / len(annotations_data) * 100):.2f}%")

    # 将移除的任务ID保存到文件中
    removed_ids_file = "/home/llz/MCP-Bench/datasets/removed_slow_tasks.txt"
    with open(removed_ids_file, 'w', encoding='utf-8') as f:
        for task_id in slow_task_ids:
            f.write(f"{task_id}\n")
    print(f"\n移除的任务ID已保存到 {removed_ids_file}")

if __name__ == "__main__":
    filter_tasks_by_execution_time()