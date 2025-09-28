#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入模块使用示例
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# 确保在正确的工作目录中
os.chdir(project_root)

def example_usage():
    """嵌入模块使用示例"""
    print("=== 嵌入模块使用示例 ===")

    # 1. 导入嵌入计算器
    from src.attacks.embedding.embedding_calculator import EmbeddingCalculator

    # 2. 初始化嵌入计算器
    calculator = EmbeddingCalculator()

    # 3. 计算文本嵌入（如果API可用）
    try:
        text = "这是一个示例文本"
        embedding = calculator.get_embeddings(text)
        print(f"1. 文本嵌入计算成功，维度: {len(embedding)}")
    except Exception as e:
        print(f"1. 文本嵌入计算失败: {e}")

    # 4. 计算向量相似度
    vec1 = [1.0, 0.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0, 0.0]
    similarity = calculator.calculate_similarity(vec1, vec2)
    print(f"2. 向量相似度: {similarity:.3f}")

    # 5. 计算多样性得分
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0]
    ]
    diversity = calculator.calculate_diversity_score(vectors)
    print(f"3. 多样性得分: {diversity:.3f}")

    # 6. 工具相似度分析
    tools = [
        {"name": "文件读取", "description": "读取文件内容"},
        {"name": "网络请求", "description": "发送HTTP请求"},
        {"name": "数据处理", "description": "处理数据"}
    ]
    similarities = calculator.calculate_tool_similarities(tools)
    print("4. 工具相似度分析:")
    for i, j, sim in similarities:
        print(f"   {tools[i]['name']} 与 {tools[j]['name']}: {sim:.3f}")

    # 7. 语义融合
    tools_with_scores = [
        {"name": "文件分析器", "description": "分析文件内容", "return_value": {"content": "..."}, "score": 0.85},
        {"name": "数据解析器", "description": "解析数据结构", "return_value": {"data": "..."}, "score": 0.78}
    ]
    fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
    print("5. 语义融合结果:")
    print(f"   融合工具名称: {fused_tool.get('name', 'N/A')}")
    print(f"   融合工具描述: {fused_tool.get('description', 'N/A')}")

if __name__ == "__main__":
    example_usage()