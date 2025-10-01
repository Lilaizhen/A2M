import json

def filter_long_tasks(all_annotations_file, long_tasks_file, output_file):
    # 读取执行时间过长的任务ID
    with open(long_tasks_file, 'r') as f:
        long_task_ids = set(line.strip() for line in f)

    print(f"找到 {len(long_task_ids)} 个执行时间过长的任务")

    # 读取原始数据集
    with open(all_annotations_file, 'r') as f:
        data = json.load(f)

    print(f"原始数据集包含 {len(data)} 个任务")

    # 过滤掉执行时间过长的任务
    filtered_data = [task for task in data if task['task_id'] not in long_task_ids]

    print(f"过滤后的数据集包含 {len(filtered_data)} 个任务")

    # 保存过滤后的数据集
    with open(output_file, 'w') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    print(f"过滤后的数据集已保存到 {output_file}")

    # 输出被删除的任务数量
    removed_count = len(data) - len(filtered_data)
    print(f"共删除了 {removed_count} 个任务")

if __name__ == "__main__":
    filter_long_tasks(
        "/home/llz/MCP-Bench/datasets/all_annotations_filtered.json",
        "/tmp/long_tasks.txt",
        "/home/llz/MCP-Bench/datasets/all_annotations_filtered_short_tasks.json"
    )