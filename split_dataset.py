#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os

def split_dataset_into_parts(input_file, output_dir, num_parts=5):
    """
    将数据集分成指定数量的部分

    Args:
        input_file: 输入的JSON文件路径
        output_dir: 输出目录路径
        num_parts: 要分成的部分数量
    """

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"总任务数: {len(data)}")

    # 计算每部分的任务数
    total_tasks = len(data)
    tasks_per_part = total_tasks // num_parts
    remainder = total_tasks % num_parts

    print(f"要分成 {num_parts} 部分")
    print(f"每部分基础任务数: {tasks_per_part}")
    print(f"余数: {remainder}")

    # 分割数据
    start_idx = 0
    for i in range(num_parts):
        # 前remainder部分会多一个任务
        end_idx = start_idx + tasks_per_part + (1 if i < remainder else 0)
        part_data = data[start_idx:end_idx]

        # 生成输出文件名
        output_file = os.path.join(output_dir, f"part_{i+1}.json")

        # 保存部分数据
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(part_data, f, ensure_ascii=False, indent=2)

        print(f"第 {i+1} 部分: {len(part_data)} 个任务，保存到 {output_file}")

        start_idx = end_idx

    # 打印统计信息
    print(f"\n分割完成!")
    print(f"输入文件: {input_file}")
    print(f"输出目录: {output_dir}")
    print(f"总任务数: {total_tasks}")
    print(f"部分数量: {num_parts}")

if __name__ == "__main__":
    input_file = "/home/llz/MCP-Bench/datasets/all_annotations_filtered_short_time_filtered.json"
    output_dir = "/home/llz/MCP-Bench/datasets/split_parts"
    split_dataset_into_parts(input_file, output_dir, 5)