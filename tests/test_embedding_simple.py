"""
简单的 Embedding 模型测试脚本（避免编码问题）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['USE_LOCAL_EMBEDDING'] = 'True'
os.environ['LOCAL_EMBEDDING_MODEL'] = 'BAAI/bge-large-zh-v1.5'
os.environ['EMBEDDING_DIM'] = '1024'

print("=" * 60)
print("Testing Embedding Model")
print("=" * 60)

try:
    from llm.client import EmbeddingClient
    
    print("\n[1] Initializing EmbeddingClient...")
    client = EmbeddingClient()
    print(f"    Client: {client}")
    
    print("\n[2] Checking availability...")
    is_available = client.is_available()
    model_info = client.get_model_info()
    
    print(f"    Available: {is_available}")
    print(f"    Mode: {model_info['mode']}")
    print(f"    Model: {model_info['model']}")
    print(f"    Dimension: {model_info['dimension']}")
    
    if not is_available:
        print("\n[ERROR] Embedding model is not available!")
        print("    Please check:")
        print("    1. sentence-transformers is installed: pip install sentence-transformers")
        print("    2. Network connection (first run needs to download model)")
        print("    3. Disk space (model is about 1.3GB)")
        sys.exit(1)
    
    print("\n[3] Testing encoding...")
    test_text = "急性胰腺炎的症状"
    embedding = client.get_embedding(test_text)
    print(f"    Text: {test_text}")
    print(f"    Vector dimension: {len(embedding)}")
    print(f"    First 5 values: {embedding[:5]}")
    
    print("\n[4] Testing batch encoding...")
    test_texts = [
        "急性胰腺炎的症状",
        "胰腺炎的治疗方法"
    ]
    embeddings = client.get_embeddings(test_texts)
    print(f"    Texts: {len(test_texts)}")
    print(f"    Embeddings: {len(embeddings)}")
    print(f"    Each dimension: {len(embeddings[0]) if embeddings else 0}")
    
    print("\n[5] Testing similarity...")
    import numpy as np
    query_vec = np.array(client.get_embedding("胰腺炎的症状"))
    desc_vec = np.array(client.get_embedding("急性胰腺炎的症状"))
    similarity = np.dot(query_vec, desc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(desc_vec))
    print(f"    Similarity: {similarity:.4f}")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Embedding model is working correctly!")
    print("=" * 60)
    
except ImportError as e:
    print(f"\n[ERROR] Import failed: {e}")
    print("    Please install: pip install sentence-transformers openai")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)





