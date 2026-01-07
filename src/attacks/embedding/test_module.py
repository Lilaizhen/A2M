#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding calculator test script - quick functional check.
"""

import sys
import os

# Add project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Ensure we run from project root
os.chdir(project_root)

def test_embedding_module():
    """Directly test the embedding module."""
    print("Directly testing embedding module...")

    # Test import
    try:
        from src.attacks.embedding.embedding_calculator import EmbeddingCalculator
        print("✓ Imported EmbeddingCalculator")
    except Exception as e:
        print(f"✗ Failed to import EmbeddingCalculator: {e}")
        return

    # Test initialization
    try:
        calculator = EmbeddingCalculator()
        print("✓ Initialized EmbeddingCalculator")
        print(f"  API Key: {calculator.api_key[:10]}..." if calculator.api_key else "  No API Key")
        print(f"  Model: {calculator.model}")
    except Exception as e:
        print(f"✗ Failed to initialize EmbeddingCalculator: {e}")
        return

    # Test similarity functions
    try:
        # Vector similarity
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = calculator.calculate_similarity(vec1, vec2)
        print(f"✓ Vector similarity: {similarity:.3f}")

        # Diversity score
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        diversity = calculator.calculate_diversity_score(vectors)
        print(f"✓ Diversity score: {diversity:.3f}")
    except Exception as e:
        print(f"✗ Similarity/diversity tests failed: {e}")

    # Test tool fusion
    try:
        tools_with_scores = [
            {"name": "Tool A", "description": "Description A", "return_value": {"result": "a"}, "score": 0.8},
            {"name": "Tool B", "description": "Description B", "return_value": {"result": "b"}, "score": 0.7}
        ]
        fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
        print(f"✓ Tool fusion test:")
        print(f"  Fused tool name: {fused_tool.get('name', 'N/A')}")
        print(f"  Fused tool description: {fused_tool.get('description', 'N/A')}")
    except Exception as e:
        print(f"✗ Tool fusion test failed: {e}")

if __name__ == "__main__":
    test_embedding_module()
