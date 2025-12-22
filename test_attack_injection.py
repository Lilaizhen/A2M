#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试攻击工具注入的脚本
"""

import json
import asyncio
from src.data_loaders.data_loader import load_dataset
from src.attacks.core.real_executor import RealExecutor

async def test_attack_injection():
    print("=" * 60)
    print("🎯 测试攻击工具注入")
    print("=" * 60)

    # 加载攻击数据集
    with open('/home/llz/MCP-Bench/attack_tools_backdoor.json', 'r') as f:
        attack_data = json.load(f)

    print(f"📊 攻击数据集包含 {len(attack_data)} 个任务")

    # 提取第一个任务的攻击工具
    first_task = attack_data[0]
    task_id = first_task['task_id']
    if task_id.startswith('task_'):
        task_id = task_id[5:]

    attack_tools = first_task['attack_tools']
    print(f"\n📝 任务ID: {task_id}")
    print(f"🔧 攻击工具数量: {len(attack_tools)}")

    # 显示攻击工具详情
    for i, tool in enumerate(attack_tools):
        print(f"\n  攻击工具 {i+1}:")
        print(f"    名称: {tool['name']}")
        print(f"    描述: {tool['description'][:100]}...")

    # 创建攻击映射
    attack_tool_mapping = {
        task_id: attack_tools
    }

    # 加载对应的任务
    all_tasks = load_dataset('./datasets/all_annotations.json')
    target_task = None
    for task in all_tasks:
        if task['id'] == task_id:
            target_task = task
            break

    if target_task:
        print(f"\n✅ 找到目标任务: {target_task['id']}")
        print(f"📝 任务描述: {target_task['description'][:100]}...")

        # 创建执行器
        executor = RealExecutor(attack=True)

        print(f"\n🚀 开始执行带攻击工具的任务...")
        # 执行单个任务
        result = await executor.execute_task_with_attack_async(target_task, attack_tools[0])

        print(f"\n📊 执行结果:")
        print(f"   任务ID: {result.get('task_id')}")
        print(f"   状态: {result.get('status')}")
        print(f"   mytool调用次数: {result.get('mytool_calls', 0)}")
        print(f"   总工具调用次数: {result.get('total_tool_calls', 0)}")

        # 检查攻击评分
        if 'attack_score' in result:
            score = result['attack_score']
            print(f"   攻击评分: {score['score']}")
            print(f"   评分原因: {score['reason']}")

        # 检查执行轨迹
        action_trace = result.get('action_trace', [])
        tool_calls = [step for step in action_trace if step.get('type') == 'tool_call']
        mytool_calls = [step for step in tool_calls if step.get('tool') == 'mytool']

        print(f"\n🔍 工具调用分析:")
        print(f"   总工具调用: {len(tool_calls)}")
        print(f"   mytool调用: {len(mytool_calls)}")

        if mytool_calls:
            print(f"\n✅ 攻击工具被成功调用！")
            for i, call in enumerate(mytool_calls):
                print(f"   调用 {i+1}: {call.get('tool', 'unknown')}")
                if 'args' in call:
                    args = call['args']
                    if isinstance(args, dict) and 'action' in args:
                        print(f"      参数: {args['action']}")
        else:
            print(f"\n⚠️  未检测到mytool调用")

    else:
        print(f"\n❌ 未找到任务 {task_id}")

if __name__ == "__main__":
    asyncio.run(test_attack_injection())
    print("\n" + "=" * 60)