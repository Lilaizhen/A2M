#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试进程级隔离
验证即使是同一个任务，每次执行都有独立的隔离环境
"""

import asyncio
import os
import time
from datetime import datetime

# 测试任务
test_task = {
    "id": "same_task_id",  # 注意：所有测试使用同一个task_id
    "description": "测试进程级隔离",
    "input": "请读取当前目录的README.md文件，看看项目是关于什么的",
    "expected_tools": ["filesystem"]
}


async def test_process_isolation():
    """测试进程级隔离"""
    print("=" * 60)
    print("测试进程级隔离")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试任务ID: {test_task['id']}")
    print(f"测试描述: 同一个任务执行3次，验证是否有3个不同的隔离目录")

    print("\n[测试开始]")

    # 运行3次同一个任务
    results = []
    process_ids = []

    for i in range(3):
        print(f"\n--- 第{i+1}次执行 ---")

        # 使用原有的并发执行接口
        from src.attacks.core.real_executor import run_tasks_as_function

        result = await run_tasks_as_function(
            dataset=[test_task],
            attack=False,
            attack_dataset=None,
            model="ZhipuAI/GLM-4.6"
        )

        # 提取进程ID
        if result['task_details']:
            process_id = result['task_details'][0].get('process_id', 'unknown')
            process_ids.append(process_id)
            print(f"  ✓ 进程ID: {process_id}")
            results.append(result)
        else:
            print(f"  ✗ 任务执行失败")

        # 等待一下，确保目录创建
        await asyncio.sleep(1)

    print("\n[隔离目录检查]")
    isolation_base = ".cache/task_isolation"
    if os.path.exists(isolation_base):
        process_dirs = [d for d in os.listdir(isolation_base) if d.startswith('process_')]
        print(f"找到 {len(process_dirs)} 个进程隔离目录:")
        for dir_name in sorted(process_dirs):
            print(f"  - {dir_name}")
            config_path = os.path.join(isolation_base, dir_name, f"mcp_config_{dir_name}.json")
            if os.path.exists(config_path):
                print(f"    ✓ MCP配置文件存在")

        # 验证每个进程ID是否唯一
        if len(set(process_ids)) == len(process_ids):
            print(f"\n✅ 验证通过：每个进程都有唯一的ID（共{len(set(process_ids))}个不同ID）")
        else:
            print(f"\n❌ 验证失败：存在重复的进程ID")

    print("\n[测试完成]")
    print("=" * 60)

    # 清理测试资源（可选）
    cleanup = input("是否清理隔离目录？(y/n): ").lower()
    if cleanup == 'y':
        from src.utils.task_isolation import cleanup_all_isolation
        cleanup_all_isolation()
        print("✓ 隔离目录已清理")


if __name__ == "__main__":
    import sys

    # 添加项目根目录到Python路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 检查API密钥
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        sys.exit(1)

    # 运行测试
    asyncio.run(test_process_isolation())
