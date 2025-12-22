import asyncio
import argparse
import os
import shutil
import json
from main_module import main as main_function
from src.data_loaders.data_loader import load_dataset
from src.utils.model_config import resolve_model, get_default_model

def reset_annotated_data():
    """重置annotated_data文件夹到备份状态"""
    annotated_data_path = os.path.join(os.getcwd(), "annotated_data")
    annotated_data_backup_path = os.path.join(os.getcwd(), "annotated_data_backup")
    
    if os.path.exists(annotated_data_path):
        shutil.rmtree(annotated_data_path)
    if os.path.exists(annotated_data_backup_path):
        shutil.copytree(annotated_data_backup_path, annotated_data_path)
    else:
        os.makedirs(annotated_data_path, exist_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # 选择数据集：all、test、filter
    parser.add_argument(
        "--dataset",
        choices=["all", "test", "filter"],
        default="all",
        help=(
            "选择数据集：\n"
            "all=./datasets/all_annotations.json（默认）\n"
            "test=./datasets/test_prompts.json\n"
            "filter=./datasets/all_annotations_filter.json"
        )
    )
    parser.add_argument("--attack", action="store_true", help="启用攻击模式 (mytool MCP server)")
    parser.add_argument("--attack-dataset", type=str, help="attack数据集路径")
    parser.add_argument("--attack-scenario", type=str, choices=["resource_waste", "task_failure", "information_leakage", "backdoor_injection", "resource_waste_no_success"], default="resource_waste", help="攻击场景类型 (默认: resource_waste)")
    parser.add_argument("--model", type=str, default=None, help="指定使用的模型名称(支持别名)")
    parser.add_argument("--judge-model", type=str, default=None, help="裁判模型名称")
    args = parser.parse_args()

    # 路径映射
    if args.dataset == "test":
        data_path = "./datasets/test_prompts.json"
    elif args.dataset == "filter":
        data_path = "./datasets/all_annotations_filter.json"
    else:  # 默认 all
        data_path = "./datasets/all_annotations.json"

    dataset = load_dataset(data_path)

    # 如果指定了攻击数据集，只执行攻击数据集中包含的任务
    filtered_dataset = dataset
    if args.attack and args.attack_dataset:
        try:
            with open(args.attack_dataset, 'r', encoding='utf-8') as f:
                attack_data = json.load(f)

            # 提取攻击数据集中的任务ID
            attack_task_ids = set()
            if isinstance(attack_data, list):
                for item in attack_data:
                    if 'task_id' in item:
                        task_id = item['task_id']
                        # 处理可能存在的 'task_' 前缀
                        if task_id.startswith('task_'):
                            task_id = task_id[5:]  # 移除 'task_' 前缀
                        attack_task_ids.add(task_id)
            elif isinstance(attack_data, dict) and 'attack_tools' in attack_data:
                # 处理单个任务的情况
                if 'task_id' in attack_data:
                    task_id = attack_data['task_id']
                    # 处理可能存在的 'task_' 前缀
                    if task_id.startswith('task_'):
                        task_id = task_id[5:]  # 移除 'task_' 前缀
                    attack_task_ids.add(task_id)

            # 过滤数据集，只保留攻击数据集中包含的任务
            if attack_task_ids:
                filtered_dataset = [task for task in dataset if task.get('id') in attack_task_ids]
                print(f"\n" + "=" * 60)
                print(f"🔍 攻击数据集过滤结果:")
                print(f"   原始数据集: {len(dataset)} 个任务")
                print(f"   攻击数据集: {len(attack_task_ids)} 个任务")
                print(f"   过滤后执行: {len(filtered_dataset)} 个任务")
                if len(filtered_dataset) < len(attack_task_ids):
                    missing_tasks = attack_task_ids - set(task.get('id') for task in filtered_dataset)
                    print(f"   未找到的任务ID: {missing_tasks}")
                print(f"=" * 60 + "\n")
            else:
                print("⚠️ 警告: 攻击数据集格式不正确，将执行所有任务")
                filtered_dataset = dataset
        except Exception as e:
            print(f"⚠️ 警告: 加载攻击数据集失败: {e}，将执行所有任务")
            filtered_dataset = dataset

    if filtered_dataset:
        # 解析模型名称
        model_name = resolve_model(args.model) if args.model else get_default_model("agent")
        judge_model = resolve_model(args.judge_model) if args.judge_model else get_default_model("judge")

        # 重置annotated_data文件夹
        reset_annotated_data()
        asyncio.run(main_function(
            filtered_dataset,
            attack=args.attack,
            attack_dataset_path=args.attack_dataset,
            attack_scenario=args.attack_scenario,
            model_name=model_name,
            judge_model=judge_model,
            dataset_type=args.dataset
        ))
    else:
        print("错误: 没有找到任何有效的数据集文件")