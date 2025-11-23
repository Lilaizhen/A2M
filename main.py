import asyncio
import argparse
import os
import shutil
from main_module import main as main_function
from src.data_loaders.data_loader import load_dataset

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
    parser.add_argument("--model", type=str, default="ZhipuAI/GLM-4.6", help="指定使用的模型名称")
    args = parser.parse_args()

    # 路径映射
    if args.dataset == "test":
        data_path = "./datasets/test_prompts.json"
    elif args.dataset == "filter":
        data_path = "./datasets/all_annotations_filter.json"
    else:  # 默认 all
        data_path = "./datasets/all_annotations.json"

    dataset = load_dataset(data_path)
    
    if dataset:
        # 重置annotated_data文件夹
        reset_annotated_data()
        asyncio.run(main_function(dataset, attack=args.attack, attack_dataset_path=args.attack_dataset, model_name=args.model, dataset_type=args.dataset))
    else:
        print("错误: 没有找到任何有效的数据集文件")