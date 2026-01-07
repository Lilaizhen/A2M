#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding module usage example.
"""

import sys
import os

# Add project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Ensure we run from project root
os.chdir(project_root)

def example_usage():
    """Example walkthrough for the embedding module."""
    print("=== Embedding module usage ===")

    # 1. Import the embedding calculator
    from src.attacks.embedding.embedding_calculator import EmbeddingCalculator

    # 2. Initialize the embedding calculator
    calculator = EmbeddingCalculator()

    # 3. Compute text embedding (if the API is available)
    try:
        text = "This is a sample text"
        embedding = calculator.get_embeddings(text)
        print(f"1. Text embedding succeeded, dimension: {len(embedding)}")
    except Exception as e:
        print(f"1. Text embedding failed: {e}")

    # 4. Calculate vector similarity
    vec1 = [1.0, 0.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0, 0.0]
    similarity = calculator.calculate_similarity(vec1, vec2)
    print(f"2. Vector similarity: {similarity:.3f}")

    # 5. Calculate diversity score
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0]
    ]
    diversity = calculator.calculate_diversity_score(vectors)
    print(f"3. Diversity score: {diversity:.3f}")

    # 6. Tool similarity analysis
    tools = [
        {"name": "File Reader", "description": "Read file contents"},
        {"name": "Network Request", "description": "Send HTTP request"},
        {"name": "Data Processor", "description": "Process data"}
    ]
    similarities = calculator.calculate_tool_similarities(tools)
    print("4. Tool similarity analysis:")
    for i, j, sim in similarities:
        print(f"   {tools[i]['name']} vs {tools[j]['name']}: {sim:.3f}")

    # 7. Semantic fusion
    tools_with_scores = [
        {"name": "File Analyzer", "description": "Analyze file contents", "return_value": {"content": "..."}, "score": 0.85},
        {"name": "Data Parser", "description": "Parse data structures", "return_value": {"data": "..."}, "score": 0.78}
    ]
    fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
    print("5. Semantic fusion result:")
    print(f"   Fused tool name: {fused_tool.get('name', 'N/A')}")
    print(f"   Fused tool description: {fused_tool.get('description', 'N/A')}")

if __name__ == "__main__":
    example_usage()
