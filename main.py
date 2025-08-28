import asyncio
import argparse
from main_module import main as main_function
from data_loaders.data_loader import load_dataset

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
    parser.add_argument("--use-mytool", action="store_true", help="启用 mytool MCP server")
    parser.add_argument("--attack-dataset", type=str, help="attack数据集路径")
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
        asyncio.run(main_function(dataset, use_mytool=args.use_mytool, attack_dataset_path=args.attack_dataset))
    else:
        print("错误: 没有找到任何有效的数据集文件")