#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the embedding utilities/tool set.
"""

import sys
import os
import json

# Add project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Ensure we are in project root
os.chdir(project_root)

# Configure SSL context via environment
import ssl
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create pool manager without strict SSL verification
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

def test_embedding_calculator():
    """Test embedding calculator behavior."""
    print("Testing embedding calculator...")

    # Use mock data to avoid API calls
    from src.attacks.embedding.embedding_calculator import EmbeddingCalculator

    # Mock calculator that does not hit real APIs
    class MockEmbeddingCalculator(EmbeddingCalculator):
        def get_embeddings(self, texts):
            """Return mock embeddings."""
            # Generate random vectors as fake embeddings
            import numpy as np
            is_single = isinstance(texts, str)
            if is_single:
                texts = [texts]

            # Produce random 4096-d vectors
            embeddings = [np.random.rand(4096).tolist() for _ in texts]
            return embeddings[0] if is_single else embeddings

    calculator = MockEmbeddingCalculator()

    # Single text embedding
    text = "This is a test text"
    embedding = calculator.get_embeddings(text)
    print(f"Single text embedding dims: {len(embedding)}")

    # Multiple texts
    texts = ["First test text", "Second test text", "Third test text"]
    embeddings = calculator.get_embeddings(texts)
    print(f"Text embeddings count: {len(embeddings)}, each dim: {len(embeddings[0])}")

    # Similarity
    similarity = calculator.calculate_similarity(embeddings[0], embeddings[1])
    print(f"Similarity of text1/text2: {similarity:.3f}")

    # Diversity score
    diversity_score = calculator.calculate_diversity_score(embeddings)
    print(f"Diversity score: {diversity_score:.3f}")

    # Tool similarity
    tools = [
        {"name": "file_reader", "description": "Read system file contents"},
        {"name": "http_client", "description": "Send HTTP requests"},
        {"name": "data_processor", "description": "Process and transform data"}
    ]

    similarities = calculator.calculate_tool_similarities(tools)
    print("\nTool similarities:")
    for i, j, sim in similarities:
        print(f"  {tools[i]['name']} vs {tools[j]['name']}: {sim:.3f}")

    # Semantic fusion
    tools_with_scores = [
        {"name": "file_reader", "description": "Read system file contents", "return_value": {"content": "file content"}, "score": 0.8},
        {"name": "data_reader", "description": "Read and parse data", "return_value": {"data": "parsed data"}, "score": 0.7}
    ]

    fused_tool = calculator.semantic_fusion(tools_with_scores, strategy="weighted")
    print(f"\nFused tool: {fused_tool['name']}")
    print(f"Fused description: {fused_tool['description']}")

if __name__ == "__main__":
    test_embedding_calculator()
