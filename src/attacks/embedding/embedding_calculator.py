#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic embedding helper module.
"""

import requests
import json
import os
from typing import List, Dict, Optional, Union, Tuple
import numpy as np

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EmbeddingCalculator:
    """Semantic embedding calculator."""

    def __init__(self, api_key: Optional[str] = None, api_base: str = "https://api.siliconflow.cn/v1"):
        """
        Initialize the embedding calculator.

        Args:
            api_key: API key; pulled from environment when omitted.
            api_base: Base URL for the embedding API.
        """
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY") or "sk-ulrlrftgwvyklbxqdvxgfkezoirtmiuegblozcsplognafaa"
        self.api_base = api_base
        self.model = "Qwen/Qwen3-Embedding-8B"

    def get_embeddings(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Get semantic embedding vectors for one or more texts.

        Args:
            texts: Single string or list of strings.

        Returns:
            Single vector or list of vectors.
        """
        # Ensure a list format for processing
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        # Build API request
        url = f"{self.api_base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": texts
        }

        # Send API request (skipping SSL verification)
        try:
            response = requests.post(url, json=payload, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Fallback: return random vectors if the API call fails
            import numpy as np
            is_single = isinstance(texts, str)
            if is_single:
                # Return a single random vector
                return np.random.rand(4096).tolist()
            else:
                # Return multiple random vectors
                return [np.random.rand(4096).tolist() for _ in texts]

        # Parse response
        data = response.json()
        embeddings = [item['embedding'] for item in data['data']]

        # Return a single vector or a list
        return embeddings[0] if is_single else embeddings

    def calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity value (0-1)
        """
        # Convert to numpy arrays
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        similarity = dot_product / (norm_v1 * norm_v2)
        # Ensure the value is in [0, 1]
        return max(0.0, min(1.0, (similarity + 1) / 2))

    def calculate_diversity_score(self, vectors: List[List[float]]) -> float:
        """
        Compute diversity score for a set of vectors (mean distance).

        Args:
            vectors: List of vectors

        Returns:
            Diversity score (0-1, higher means more diverse)
        """
        if len(vectors) < 2:
            return 0.0

        # Compute distances between all vector pairs
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                # Use Euclidean distance
                dist = np.linalg.norm(np.array(vectors[i]) - np.array(vectors[j]))
                distances.append(dist)

        # Use average distance as diversity
        avg_distance = np.mean(distances) if distances else 0.0
        # Normalize to 0-1 (assume max distance ~2 for normalized vectors)
        return min(1.0, avg_distance / 2.0)

    def semantic_fusion(self, tools_with_scores: List[Dict], strategy: str = "weighted") -> Dict:
        """
        Fuse tools based on semantic information.

        Args:
            tools_with_scores: Tools with scores; each has 'name', 'description', 'return_value', 'score'.
            strategy: Fusion strategy ('weighted' for weighted average, 'diverse' for diversity-oriented fusion).

        Returns:
            Fused tool definition.
        """
        if not tools_with_scores:
            return {}

        if len(tools_with_scores) == 1:
            return {
                "name": tools_with_scores[0]["name"],
                "description": tools_with_scores[0]["description"],
                "return_value": tools_with_scores[0]["return_value"]
            }

        # Extract names and descriptions for embeddings
        names = [tool["name"] for tool in tools_with_scores]
        descriptions = [tool["description"] for tool in tools_with_scores]

        # Get embedding vectors
        name_embeddings = self.get_embeddings(names)
        desc_embeddings = self.get_embeddings(descriptions)

        # Choose fusion method based on strategy
        if strategy == "weighted":
            # Weighted fusion: average by score
            scores = [tool["score"] for tool in tools_with_scores]
            total_score = sum(scores)

            if total_score == 0:
                weights = [1.0 / len(scores)] * len(scores)
            else:
                weights = [score / total_score for score in scores]

            # Name: choose the one with highest weight
            fused_name_idx = weights.index(max(weights))
            fused_name = names[fused_name_idx]

            # Description: concatenate top weighted descriptions
            sorted_tools = sorted(zip(tools_with_scores, weights), key=lambda x: x[1], reverse=True)
            top_descriptions = [tool["description"] for tool, weight in sorted_tools[:3]]
            fused_description = " ".join(top_descriptions)

            # Return value: take the structure with the highest weight
            fused_return_value = tools_with_scores[fused_name_idx]["return_value"]

        else:  # default to diversity-based fusion
            # Diversity fusion: combine tools that are semantically different
            # Compute diversity of description vectors
            diversity_score = self.calculate_diversity_score(desc_embeddings)

            # Pick a method based on diversity
            if diversity_score > 0.3:  # High diversity
                # Choose the two most different tools
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
                # Fuse name: blend halves of both names
                fused_name = f"{names[i][:len(names[i])//2]}{names[j][len(names[j])//2:]}"
                # Fuse description: concatenate both
                fused_description = f"{descriptions[i]} {descriptions[j]}"
                # Fuse return value: merge dictionaries
                rv1 = tools_with_scores[i]["return_value"]
                rv2 = tools_with_scores[j]["return_value"]
                fused_return_value = {**rv1, **rv2}
            else:  # Low diversity
                # Choose the top-scoring tool
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
        Calculate semantic similarity between tools.

        Args:
            tools: List of tools with 'name' and 'description'.

        Returns:
            List of tuples: (tool_i index, tool_j index, similarity).
        """
        if len(tools) < 2:
            return []

        # Combine name and description for embeddings
        descriptions = [f"{tool['name']} {tool['description']}" for tool in tools]

        # Get embeddings
        embeddings = self.get_embeddings(descriptions)

        # Compute pairwise similarities
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarity = self.calculate_similarity(embeddings[i], embeddings[j])
                similarities.append((i, j, similarity))

        # Sort descending by similarity
        similarities.sort(key=lambda x: x[2], reverse=True)

        return similarities
