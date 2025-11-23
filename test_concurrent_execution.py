#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试并发执行和任务隔离
"""

import os
import time
import asyncio
import psutil
from datetime import datetime
from src.attacks.core.real_executor import RealExecutor

# 测试任务
test_dataset = [
    {
        "id": "test_task_1",
        "description": "测试任务1：分析当前目录的项目结构",
        "input": "请使用文件系统工具分析当前目录的项目结构，看有哪些主要文件和文件夹",
        "expected_tools": ["filesystem"]
    },
    {
        "id": "test_task_2",
        "description": "测试任务2：查看文件内容",
        "input": "请读取项目根目录下的 main.py 文件内容",
        "expected_tools": ["filesystem", "text-editor"]
    },
    {
        "id": "test_task_3",
        "description": "测试任务3：查看README",
        "input": "请读取README.md文件的内容",
        "expected_tools": ["filesystem"]
    }
]


def get_system_resources():
    """获取系统资源使用情况"""
    process = psutil.Process()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": memory.used / (1024**3),
        "process_memory_mb": process.memory_info().rss / (1024**2)
    }


def test_concurrent_execution():
    """测试并发执行"""
    print("=" * 60)
    print("测试并发执行和任务隔离")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试任务数量: {len(test_dataset)}")

    # 记录测试前的资源使用情况
    print("\n[资源监控] 测试前系统资源:")
    resources_before = get_system_resources()
    print(f"  CPU使用率: {resources_before['cpu_percent']:.1f}%")
    print(f"  内存使用率: {resources_before['memory_percent']:.1f}%")
    print(f"  内存使用: {resources_before['memory_used_gb']:.2f} GB")
    print(f"  当前进程内存: {resources_before['process_memory_mb']:.2f} MB")

    # 估算串行执行时间（单任务平均时间 * 任务数）
    print("\n[性能预估] 串行 vs 并发:")
    print(f"  任务数量: {len(test_dataset)}")
    print(f"  串行估计时间: ~180 秒 (60秒/任务)")
    print(f"  并发估计时间: ~60 秒 (限制3个并行)")
    print(f"  预期加速比: ~3x")

    # 测试基线执行（可以同时测试无攻击下的性能）
    print("\n1. 并发执行中...")
    start_time = time.time()

    # 使用run_tasks_as_function并发执行
    from src.attacks.core.real_executor import run_tasks_as_function

    async def run_concurrent_test():
        result = await run_tasks_as_function(
            dataset=test_dataset,
            attack=False,
            attack_dataset=None,
            model="ZhipuAI/GLM-4.6"
        )
        return result

    result = asyncio.run(run_concurrent_test())
    end_time = time.time()
    total_time = end_time - start_time

    end_time = time.time()
    total_time = end_time - start_time

    # 打印结果
    print(f"\n执行完成！")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"任务完成率: {result['overall_statistics']['task_completion_rate']}")
    print(f"总工具调用次数: {result['overall_statistics']['total_tool_calls']}")

    # 打印每个任务的详细信息
    print("\n任务执行详情:")
    for task_result in result['task_details']:
        print(f"\n- Task ID: {task_result['task_id']}")
        print(f"  完成状态: {task_result['task_completed']}")
        print(f"  耗时: {task_result['execution_time_seconds']:.2f} 秒")
        print(f"  工具调用: {task_result['total_tool_calls']} 次")

    # 检查隔离目录
    print("\n2. 检查任务隔离目录...")
    isolation_base = ".cache/task_isolation"
    if os.path.exists(isolation_base):
        task_dirs = os.listdir(isolation_base)
        print(f"找到 {len(task_dirs)} 个任务隔离目录:")
        for task_dir in sorted(task_dirs):
            if task_dir.startswith("test_task_"):
                print(f"  - {task_dir}")
                annotated_path = os.path.join(isolation_base, task_dir, "annotated_data")
                if os.path.exists(annotated_path):
                    print(f"    ✓ annotated_data 存在")
                    mcp_config_path = os.path.join(isolation_base, task_dir, f"mcp_config_{task_dir}.json")
                    if os.path.exists(mcp_config_path):
                        print(f"    ✓ MCP配置文件存在")

    print("\n3. 验证文件隔离...")
    for i, task in enumerate(test_dataset):
        task_id = task['id']
        annotated_path = os.path.join(isolation_base, task_id, "annotated_data")
        if os.path.exists(annotated_path):
            # 检查是否有文件被修改（理论上不应该有，因为是读取操作）
            files = []
            if os.path.isdir(annotated_path):
                for item in os.listdir(annotated_path):
                    item_path = os.path.join(annotated_path, item)
                    if os.path.isfile(item_path):
                        files.append(item)
            print(f"  任务 {task_id}: 隔离目录中的文件数: {len(files)}")

    # 清理测试资源
    # 记录测试后的资源使用情况
    print("\n[资源监控] 测试后系统资源:")
    resources_after = get_system_resources()
    print(f"  CPU使用率: {resources_after['cpu_percent']:.1f}%")
    print(f"  内存使用率: {resources_after['memory_percent']:.1f}%")
    print(f"  内存使用: {resources_after['memory_used_gb']:.2f} GB")
    print(f"  当前进程内存: {resources_after['process_memory_mb']:.2f} MB")
    print(f"  内存增量: {resources_after['process_memory_mb'] - resources_before['process_memory_mb']:.2f} MB")

    print("\n4. 验证文件系统隔离...")
    for i, task in enumerate(test_dataset):
        task_id = task['id']
        annotated_path = os.path.join(isolation_base, task_id, "annotated_data")
        if os.path.exists(annotated_path):
            files = []
            if os.path.isdir(annotated_path):
                for item in os.listdir(annotated_path):
                    item_path = os.path.join(annotated_path, item)
                    if os.path.isfile(item_path):
                        files.append(item)
            print(f"  任务 {task_id}: 隔离目录中的文件数: {len(files)}")

    print("\n5. 清理测试资源...")
    from src.utils.task_isolation import cleanup_all_isolation
    cleanup_all_isolation()
    print("✓ 所有隔离目录已清理")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    import os
    import sys

    # 添加项目根目录到Python路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 检查API密钥
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        sys.exit(1)

    # 运行测试
    try:
        test_concurrent_execution()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
