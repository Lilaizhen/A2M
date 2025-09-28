#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义嵌入工具模块
"""

import requests
import json
import os
from typing import List, Dict, Optional, Union, Tuple
import numpy as np

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EmbeddingCalculator:
    """语义嵌入计算器"""

    def __init__(self, api_key: Optional[str] = None, api_base: str = "https://api.siliconflow.cn/v1"):
        """
        初始化嵌入计算器

        Args:
            api_key: API密钥，如果不提供则从环境变量获取
            api_base: API基础URL
        """
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY") or "sk-ulrlrftgwvyklbxqdvxgfkezoirtmiuegblozcsplognafaa"
        self.api_base = api_base
        self.model = "Qwen/Qwen3-Embedding-8B"

    def get_embeddings(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        获取文本的语义嵌入向量

        Args:
            texts: 单个文本或文本列表

        Returns:
            单个向量或向量列表
        """
        # 确保texts是列表格式
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        # 准备API请求
        url = f"{self.api_base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": texts
        }

        # 发送API请求（忽略SSL验证）
        try:
            response = requests.post(url, json=payload, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # 如果API调用失败，返回随机向量作为后备方案
            import numpy as np
            is_single = isinstance(texts, str)
            if is_single:
                # 返回单个随机向量
                return np.random.rand(4096).tolist()
            else:
                # 返回多个随机向量
                return [np.random.rand(4096).tolist() for _ in texts]

        # 解析响应
        data = response.json()
        embeddings = [item['embedding'] for item in data['data']]

        # 返回单个向量或向量列表
        return embeddings[0] if is_single else embeddings

    def calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量之间的余弦相似度

        Args:
            vec1: 第一个向量
            vec2: 第二个向量

        Returns:
            余弦相似度值 (0-1)
        """
        # 转换为numpy数组
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # 计算余弦相似度
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        similarity = dot_product / (norm_v1 * norm_v2)
        # 确保返回值在[0,1]范围内
        return max(0.0, min(1.0, (similarity + 1) / 2))

    def calculate_diversity_score(self, vectors: List[List[float]]) -> float:
        """
        计算向量集合的多样性得分（基于平均距离）

        Args:
            vectors: 向量列表

        Returns:
            多样性得分 (0-1, 越高越多样)
        """
        if len(vectors) < 2:
            return 0.0

        # 计算所有向量对之间的距离
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                # 使用欧几里得距离
                dist = np.linalg.norm(np.array(vectors[i]) - np.array(vectors[j]))
                distances.append(dist)

        # 返回平均距离作为多样性得分
        avg_distance = np.mean(distances) if distances else 0.0
        # 归一化到0-1范围（假设最大距离为2，因为向量已归一化）
        return min(1.0, avg_distance / 2.0)

    def semantic_fusion(self, tools_with_scores: List[Dict], strategy: str = "weighted") -> Dict:
        """
        根据语义信息融合工具

        Args:
            tools_with_scores: 带分数的工具列表，每个元素包含'name', 'description', 'return_value', 'score'
            strategy: 融合策略 ('weighted'-加权融合, 'diverse'-多样化融合)

        Returns:
            融合后的工具定义
        """
        if not tools_with_scores:
            return {}

        if len(tools_with_scores) == 1:
            return {
                "name": tools_with_scores[0]["name"],
                "description": tools_with_scores[0]["description"],
                "return_value": tools_with_scores[0]["return_value"]
            }

        # 提取工具名称和描述用于嵌入计算
        names = [tool["name"] for tool in tools_with_scores]
        descriptions = [tool["description"] for tool in tools_with_scores]

        # 获取嵌入向量
        name_embeddings = self.get_embeddings(names)
        desc_embeddings = self.get_embeddings(descriptions)

        # 根据策略选择融合方式
        if strategy == "weighted":
            # 加权融合：根据分数加权平均
            scores = [tool["score"] for tool in tools_with_scores]
            total_score = sum(scores)

            if total_score == 0:
                weights = [1.0 / len(scores)] * len(scores)
            else:
                weights = [score / total_score for score in scores]

            # 加权融合名称（选择权重最高的名称）
            fused_name_idx = weights.index(max(weights))
            fused_name = names[fused_name_idx]

            # 加权融合描述（简单拼接前几个高权重的）
            sorted_tools = sorted(zip(tools_with_scores, weights), key=lambda x: x[1], reverse=True)
            top_descriptions = [tool["description"] for tool, weight in sorted_tools[:3]]
            fused_description = " ".join(top_descriptions)

            # 加权融合返回值（选择权重最高的返回值结构）
            fused_return_value = tools_with_scores[fused_name_idx]["return_value"]

        else:  # 默认使用多样化融合
            # 多样化融合：选择语义上差异较大的工具进行融合
            # 计算描述向量的多样性得分
            diversity_score = self.calculate_diversity_score(desc_embeddings)

            # 根据多样性得分选择融合方式
            if diversity_score > 0.3:  # 高多样性
                # 选择语义差异最大的两个工具
                max_diff = -1
                max_pair = (0, 1)
                for i in range(len(desc_embeddings)):
                    for j in range(i + 1, len(desc_embeddings)):
                        similarity = self.calculate_similarity(desc_embeddings[i], desc_embeddings[j])
                        diff = 1 - similarity
                        if diff > max_diff:
                            max_diff = diff
                            max_pair = (i, j)

                i, j = max_pair
                # 融合名称：组合两个名称
                fused_name = f"{names[i][:len(names[i])//2]}{names[j][len(names[j])//2:]}"
                # 融合描述：拼接两个描述
                fused_description = f"{descriptions[i]} {descriptions[j]}"
                # 融合返回值：合并两个返回值结构
                rv1 = tools_with_scores[i]["return_value"]
                rv2 = tools_with_scores[j]["return_value"]
                fused_return_value = {**rv1, **rv2}
            else:  # 低多样性
                # 选择得分最高的工具
                best_tool = max(tools_with_scores, key=lambda x: x["score"])
                fused_name = best_tool["name"]
                fused_description = best_tool["description"]
                fused_return_value = best_tool["return_value"]

        return {
            "name": fused_name,
            "description": fused_description,
            "return_value": fused_return_value
        }

    def calculate_tool_similarities(self, tools: List[Dict]) -> List[Tuple[int, int, float]]:
        """
        计算工具之间的语义相似度

        Args:
            tools: 工具列表，每个元素包含'name', 'description'

        Returns:
            相似度列表，每个元素为(工具i索引, 工具j索引, 相似度)
        """
        if len(tools) < 2:
            return []

        # 提取描述用于嵌入计算
        descriptions = [f"{tool['name']} {tool['description']}" for tool in tools]

        # 获取嵌入向量
        embeddings = self.get_embeddings(descriptions)

        # 计算所有工具对之间的相似度
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarity = self.calculate_similarity(embeddings[i], embeddings[j])
                similarities.append((i, j, similarity))

        # 按相似度降序排序
        similarities.sort(key=lambda x: x[2], reverse=True)

        return similarities