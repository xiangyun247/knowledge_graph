# Embedding 模型接入说明

## ✅ 已完成的修改

### 1. 更新 `llm/client.py` 中的 `EmbeddingClient` 类

- ✅ 支持使用本地模型（sentence-transformers）
- ✅ 支持使用 API 服务（OpenAI 兼容）
- ✅ 自动降级到占位向量（如果以上都不可用）
- ✅ 自动从 `config.py` 读取配置
- ✅ 支持批量编码（提高效率）
- ✅ 向量归一化（提高相似度计算准确性）

### 2. 配置说明

在 `.env` 文件中配置：

```env
# 使用本地模型（推荐）
USE_LOCAL_EMBEDDING=True
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIM=1024
```

### 3. 测试脚本

已创建 `tests/test_embedding.py` 用于测试模型加载和功能。

## 🚀 使用步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

确保已安装：
- `sentence-transformers==2.2.2`
- `torch>=2.0.0`

### 2. 配置环境变量

在 `.env` 文件中设置：

```env
USE_LOCAL_EMBEDDING=True
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIM=1024
```

### 3. 测试模型加载

```bash
python tests/test_embedding.py
```

首次运行会自动下载模型（约 1.3GB），请确保：
- 网络连接正常
- 磁盘空间充足（至少 2GB）

### 4. 在代码中使用

```python
from llm.client import EmbeddingClient

# 初始化（自动从 config 读取配置）
embedding_client = EmbeddingClient()

# 检查是否可用
if embedding_client.is_available():
    print("✅ Embedding 模型可用")
    
    # 获取单个文本的向量
    embedding = embedding_client.get_embedding("急性胰腺炎的症状")
    print(f"向量维度: {len(embedding)}")
    
    # 批量获取向量
    embeddings = embedding_client.get_embeddings([
        "急性胰腺炎的症状",
        "胰腺炎的治疗方法"
    ])
    
    # 获取模型信息
    info = embedding_client.get_model_info()
    print(f"模型信息: {info}")
else:
    print("⚠️  Embedding 模型不可用，使用占位向量")
```

## 📊 模型信息

- **模型名称**: `BAAI/bge-large-zh-v1.5`
- **向量维度**: 1024
- **模型大小**: 约 1.3GB
- **特点**: 
  - 专为中文优化
  - 支持长文本（最多 512 tokens）
  - 语义理解能力强
  - 适合医疗领域问答

## 🔍 工作原理

1. **初始化时**：
   - 如果 `USE_LOCAL_EMBEDDING=True`，尝试加载本地模型
   - 如果本地模型加载失败，尝试使用 API（如果配置了 API key）
   - 如果都不可用，使用占位向量（零向量）

2. **编码时**：
   - 使用 `sentence-transformers` 将文本转换为向量
   - 自动归一化向量（提高相似度计算准确性）
   - 支持批量处理（提高效率）

3. **在 RAG 中使用**：
   - `rag_pipeline.py` 中的 `_vector_search` 方法会使用 Embedding 进行向量检索
   - 计算查询向量与知识库文本的余弦相似度
   - 返回最相似的 Top-K 结果

## ⚠️ 注意事项

1. **首次下载**：模型首次下载可能需要较长时间，请耐心等待
2. **内存占用**：模型加载后会占用约 2-3GB 内存
3. **GPU 加速**：如果有 GPU，会自动使用 GPU 加速（需要安装 CUDA 版本的 PyTorch）
4. **CPU 模式**：如果没有 GPU，也可以在 CPU 上运行，但速度较慢

## 🐛 故障排除

### 问题 1: 模型下载失败

**解决方案**：
- 检查网络连接
- 尝试使用 HuggingFace 镜像源
- 手动下载模型到本地缓存目录

### 问题 2: 内存不足

**解决方案**：
- 使用更小的模型（如 `BAAI/bge-base-zh-v1.5`，768 维）
- 减少批量处理的大小
- 增加系统内存

### 问题 3: 编码速度慢

**解决方案**：
- 使用 GPU 加速（安装 CUDA 版本的 PyTorch）
- 减少批量处理的大小
- 使用更小的模型

## 📝 相关文件

- `llm/client.py` - EmbeddingClient 实现
- `config.py` - 配置管理
- `rag/rag_pipeline.py` - RAG 流水线（使用 Embedding）
- `tests/test_embedding.py` - 测试脚本

## 🔗 相关链接

- [BAAI/bge-large-zh-v1.5 模型页面](https://huggingface.co/BAAI/bge-large-zh-v1.5)
- [sentence-transformers 文档](https://www.sbert.net/)
- [HuggingFace 模型库](https://huggingface.co/models)





