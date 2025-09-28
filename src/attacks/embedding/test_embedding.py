#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具集合管理器测试脚本
"""

import sys
import os
import json

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# 确保在正确的工作目录中
os.chdir(project_root)

# 使用环境变量设置SSL上下文
import ssl
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 创建不验证SSL的池管理器
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

def test_embedding_calculator():
    """测试嵌入计算器功能"""
    print("测试嵌入计算器...")

    # 由于API连接问题，我们使用模拟数据进行测试
    from src.attacks.embedding.embedding_calculator import EmbeddingCalculator

    # 创建一个模拟的嵌入计算器（不实际调用API）
    class MockEmbeddingCalculator(EmbeddingCalculator):
        def get_embeddings(self, texts):
            """模拟嵌入获取"""
            # 返回随机向量作为模拟嵌入
            import numpy as np
            is_single = isinstance(texts, str)
            if is_single:
                texts = [texts]

            # 生成随机向量（4096维）
            embeddings = [np.random.rand(4096).tolist() for _ in texts]
            return embeddings[0] if is_single else embeddings

    calculator = MockEmbeddingCalculator()

    # 测试单个文本嵌入
    text = "这是一个测试文本"
    embedding = calculator.get_embeddings(text)
    print(f"单个文本嵌入维度: {len(embedding)}")

    # 测试多个文本嵌入
    texts = ["这是第一个测试文本", "这是第二个测试文本", "这是第三个测试文本"]
    embeddings = calculator.get_embeddings(texts)
    print(f"多个文本嵌入数量: {len(embeddings)}, 每个维度: {len(embeddings[0])}")

    # 测试相似度计算
    similarity = calculator.calculate_similarity(embeddings[0], embeddings[1])
    print(f"文本1和文本2的相似度: {similarity:.3f}")

    # 测试多样性得分
    diversity_score = calculator.calculate_diversity_score(embeddings)
    print(f"文本集合的多样性得分: {diversity_score:.3f}")

    # 测试工具相似度计算
    tools = [
        {"name": "文件读取工具", "description": "用于读取系统文件内容"},
        {"name": "网络请求工具", "description": "用于发送HTTP网络请求"},
        {"name": "数据处理工具", "description": "用于处理和转换数据"}
    ]

    similarities = calculator.calculate_tool_similarities(tools)
    print("\n工具间相似度:")
    for i, j, sim in similarities:
        print(f"  {tools[i]['name']} 与 {tools[j]['name']}: {sim:.3f}")

    # 测试语义融合
    tools_with_scores = [
        {"name": "文件读取工具", "description": "用于读取系统文件内容", "return_value": {"content": "file content"}, "score": 0.8},
        {"name": "数据读取工具", "description": "用于读取和解析数据", "return_value": {"data": "parsed data"}, "score": 0.7}
    ]

    fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
    print(f"\n融合工具: {fused_tool['name']}")
    print(f"融合描述: {fused_tool['description']}")

if __name__ == "__main__":
    test_embedding_calculator()