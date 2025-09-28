#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入计算器测试脚本 - 直接测试模块功能
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# 确保在正确的工作目录中
os.chdir(project_root)

def test_embedding_module():
    """直接测试嵌入模块的功能"""
    print("直接测试嵌入模块功能...")

    # 测试导入
    try:
        from src.attacks.embedding.embedding_calculator import EmbeddingCalculator
        print("✓ 成功导入EmbeddingCalculator")
    except Exception as e:
        print(f"✗ 导入EmbeddingCalculator失败: {e}")
        return

    # 测试初始化
    try:
        calculator = EmbeddingCalculator()
        print("✓ 成功初始化EmbeddingCalculator")
        print(f"  API Key: {calculator.api_key[:10]}..." if calculator.api_key else "  无API Key")
        print(f"  Model: {calculator.model}")
    except Exception as e:
        print(f"✗ 初始化EmbeddingCalculator失败: {e}")
        return

    # 测试相似度计算功能
    try:
        # 测试向量相似度计算
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = calculator.calculate_similarity(vec1, vec2)
        print(f"✓ 向量相似度计算: {similarity:.3f}")

        # 测试多样性得分计算
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        diversity = calculator.calculate_diversity_score(vectors)
        print(f"✓ 多样性得分计算: {diversity:.3f}")
    except Exception as e:
        print(f"✗ 相似度计算功能测试失败: {e}")

    # 测试工具融合功能
    try:
        tools_with_scores = [
            {"name": "工具A", "description": "描述A", "return_value": {"result": "a"}, "score": 0.8},
            {"name": "工具B", "description": "描述B", "return_value": {"result": "b"}, "score": 0.7}
        ]
        fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
        print(f"✓ 工具融合功能测试:")
        print(f"  融合工具名称: {fused_tool.get('name', 'N/A')}")
        print(f"  融合工具描述: {fused_tool.get('description', 'N/A')}")
    except Exception as e:
        print(f"✗ 工具融合功能测试失败: {e}")

if __name__ == "__main__":
    test_embedding_module()