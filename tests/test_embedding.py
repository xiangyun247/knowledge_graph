"""
测试 Embedding 模型加载和功能

用于验证 BAAI/bge-large-zh-v1.5 模型是否能正常加载和使用
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from llm.client import EmbeddingClient
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_embedding_model():
    """测试 Embedding 模型"""
    print("\n" + "=" * 60)
    print("🧪 测试 Embedding 模型加载和功能")
    print("=" * 60)
    
    # 显示配置
    print(f"\n📋 配置信息:")
    print(f"   USE_LOCAL_EMBEDDING: {config.USE_LOCAL_EMBEDDING}")
    print(f"   LOCAL_EMBEDDING_MODEL: {config.LOCAL_EMBEDDING_MODEL}")
    print(f"   EMBEDDING_DIM: {config.EMBEDDING_DIM}")
    
    # 初始化客户端
    print(f"\n🔄 正在初始化 Embedding 客户端...")
    try:
        embedding_client = EmbeddingClient()
        print(f"✅ 客户端初始化成功")
        print(f"   {embedding_client}")
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 检查是否可用
    print(f"\n🔍 检查模型可用性...")
    is_available = embedding_client.is_available()
    model_info = embedding_client.get_model_info()
    
    print(f"   可用状态: {'✅ 可用' if is_available else '❌ 不可用（使用占位向量）'}")
    print(f"   模式: {model_info['mode']}")
    print(f"   模型: {model_info['model']}")
    print(f"   维度: {model_info['dimension']}")
    
    if not is_available:
        print(f"\n⚠️  警告: Embedding 模型不可用，向量检索功能将无法正常工作")
        print(f"   请检查:")
        print(f"   1. sentence-transformers 是否已安装: pip install sentence-transformers")
        print(f"   2. 网络连接是否正常（首次运行需要下载模型）")
        print(f"   3. 磁盘空间是否充足（模型约 1.3GB）")
        return False
    
    # 测试编码功能
    print(f"\n🧪 测试文本编码功能...")
    test_texts = [
        "急性胰腺炎的症状",
        "胰腺发炎了会有什么表现",
        "如何治疗胰腺炎",
        "胰腺炎的并发症有哪些"
    ]
    
    try:
        # 单个文本编码
        print(f"\n   测试单个文本编码...")
        test_text = test_texts[0]
        embedding = embedding_client.get_embedding(test_text)
        print(f"   ✅ 编码成功")
        print(f"   文本: {test_text}")
        print(f"   向量维度: {len(embedding)}")
        print(f"   向量前5维: {embedding[:5]}")
        
        # 批量编码
        print(f"\n   测试批量文本编码...")
        embeddings = embedding_client.get_embeddings(test_texts)
        print(f"   ✅ 批量编码成功")
        print(f"   文本数量: {len(test_texts)}")
        print(f"   向量数量: {len(embeddings)}")
        print(f"   每个向量维度: {len(embeddings[0]) if embeddings else 0}")
        
    except Exception as e:
        print(f"   ❌ 编码测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试语义相似度
    print(f"\n🔍 测试语义相似度计算...")
    try:
        from rag.rag_pipeline import RAGPipeline
        
        # 计算相似度
        query_embedding = embedding_client.get_embedding("胰腺炎的症状")
        desc_embedding = embedding_client.get_embedding("急性胰腺炎的症状")
        
        # 余弦相似度
        import numpy as np
        query_vec = np.array(query_embedding)
        desc_vec = np.array(desc_embedding)
        similarity = np.dot(query_vec, desc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(desc_vec))
        
        print(f"   ✅ 相似度计算成功")
        print(f"   查询: '胰腺炎的症状'")
        print(f"   描述: '急性胰腺炎的症状'")
        print(f"   相似度: {similarity:.4f}")
        
        # 测试不同语义的文本
        different_embedding = embedding_client.get_embedding("糖尿病的治疗方法")
        different_vec = np.array(different_embedding)
        different_similarity = np.dot(query_vec, different_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(different_vec))
        
        print(f"   查询: '胰腺炎的症状'")
        print(f"   描述: '糖尿病的治疗方法'")
        print(f"   相似度: {different_similarity:.4f}")
        
        if similarity > different_similarity:
            print(f"   ✅ 语义相似度计算正确（相关文本相似度更高）")
        else:
            print(f"   ⚠️  语义相似度可能有问题")
            
    except Exception as e:
        print(f"   ⚠️  相似度测试失败: {e}")
        print(f"   （这可能是正常的，如果 numpy 未安装）")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Embedding 模型测试完成")
    print(f"=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_embedding_model()
    sys.exit(0 if success else 1)





