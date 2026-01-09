# 大规模医学知识图谱生成与智能问答系统

## 项目简介

本项目是一个功能完整的大规模医学知识图谱生成与智能问答系统，基于 Docker、Hadoop 和 Celery 构建，实现了从 PDF/文本数据到知识图谱的全流程自动化，以及基于知识图谱的智能问答和 RAG 检索功能。

### 核心功能

✅ **知识图谱生成**：支持从 PDF、纯文本、JSON 等多种数据源生成医学知识图谱
✅ **智能问答系统**：基于知识图谱和 LLM 的智能问答，支持多意图识别
✅ **RAG 检索**：融合图检索、向量检索和混合检索的 RAG 流水线
✅ **分布式处理**：基于 Hadoop 的分布式文本处理，支持大规模数据
✅ **异步任务管理**：基于 Celery 的异步任务队列，支持批量任务处理
✅ **多数据库支持**：Neo4j 图数据库 + MySQL 关系型数据库，实现数据持久化
✅ **RESTful API**：完整的 API 服务，支持知识图谱查询、数据导入等
✅ **Docker 容器化**：全系统容器化，支持快速部署和环境一致性

## 系统架构

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                  用户层                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────────────┐   │
│  │ API调用 │  │ Web界面 │  │ 测试脚本 │  │ 外部系统集成（可选）        │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └──────────────┬────────────┘   │
└───────┼───────────┼────────────┼───────────────────────┼───────────────┘
        │           │            │                       │
┌───────▼───────────▼────────────▼───────────────────────▼───────────────┐
│                                  API层                                   │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                        FastAPI 服务                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │   │
│  │  │ 健康检查│  │ 统计查询│  │ 实体搜索│  │ 智能问答│  │ 数据导入│   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                业务逻辑层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    知识图谱生成  │  │    智能问答处理  │  │    RAG 流水线    │  │ 任务管理 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    实体提取器    │  │    意图识别器    │  │    向量嵌入器    │  │ LLM调用 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                数据处理层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    Hadoop 分布式处理│  │    Celery 异步任务│  │    PDF 提取处理  │  │ 文本处理 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │   │
│  │    文本清理      │  │    文本分块      │  │    实体关系提取  │             │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                数据存储层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    Neo4j 图数据库  │  │    MySQL 关系数据库  │  │    HDFS 分布式存储 │  │ 本地存储 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

## 核心技术栈

| 技术类别 | 核心技术 | 版本/说明 |
|---------|---------|-----------|
| 容器化 | Docker | 20.10+ |
| 分布式处理 | Hadoop | 3.3.0+ |
| 异步任务 | Celery | 5.3+ |
| 图数据库 | Neo4j | 4.4+ |
| 关系数据库 | MySQL | 8.0+ |
| API 框架 | FastAPI | 0.100+ |
| 编程语言 | Python | 3.8+ |
| LLM | DeepSeek API | - |
| 向量嵌入 | BAAI/bge-large-zh-v1.5 | - |
| 知识图谱构建 | 自定义算法 | 基于 LLM 的实体关系提取 |

## 功能模块详细说明

### 1. 知识图谱生成

**核心功能**：从多种数据源生成医学知识图谱

- **支持的数据源**：
  - PDF 文档（通过 Hadoop 分布式提取）
  - 纯文本文件
  - JSON 格式数据
  - 批量数据处理

- **生成流程**：
  1. 数据导入（本地或 HDFS）
  2. 文本清理和预处理
  3. 文本分块（1000 字符/段落）
  4. 基于 LLM 的实体-关系提取
  5. 知识图谱构建
  6. 数据持久化（Neo4j + MySQL）

### 2. 智能问答系统

**核心功能**：基于知识图谱的智能问答，支持多意图识别

- **问答类型**：
  - 症状查询（例如："高血压有什么症状？"）
  - 治疗查询（例如："糖尿病怎么治疗？"）
  - 科室查询（例如："感冒应该看什么科？"）
  - 病因查询（例如："头痛可能是什么病？"）
  - 药物查询（例如："二甲双胍有什么作用？"）

- **问答流程**：
  1. 用户提问
  2. 意图识别和实体提取
  3. 知识图谱查询
  4. 回答生成
  5. 结果返回

### 3. RAG 检索

**核心功能**：融合多种检索方式的 RAG 流水线

- **检索策略**：
  - 图检索（基于 Neo4j 图数据库）
  - 向量检索（基于文本嵌入）
  - 混合检索（图+向量）
  - 关键词检索（备用方案）

- **RAG 流程**：
  1. 查询解析
  2. 信息检索
  3. 上下文构建
  4. 答案生成
  5. 结果返回

### 4. API 服务

**核心功能**：完整的 RESTful API 服务

- **主要端点**：
  - `/health` - 健康检查
  - `/stats` - 获取知识图谱统计信息
  - `/search` - 搜索实体
  - `/query` - 智能问答
  - `/api/import` - 数据导入

## 安装和部署

### 1. 环境准备

- Docker 20.10+
- Docker Compose 1.29+
- Python 3.8+（本地开发）

### 2. 快速启动

```bash
# 1. 克隆项目
git clone <项目地址>
cd knowledge_gragh

# 2. 复制配置文件
cp .env.example .env

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps
```

### 3. 本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动数据库服务
docker-compose up -d neo4j mysql

# 3. 启动 API 服务
python api_server.py

# 4. 启动 Celery 服务
celery -A backend.celery_app worker --loglevel=info
```

## 使用指南

### 1. 知识图谱生成

#### 从文本生成

```python
from kg.builder import KnowledgeGraphBuilder
from db.mysql_client import MySQLClient

# 初始化构建器
builder = KnowledgeGraphBuilder()

# 初始化 MySQL 客户端
mysql_client = MySQLClient()

# 生成知识图谱
text = "胰腺炎是胰腺因胰蛋白酶的自身消化作用而引起的疾病。"
graph = builder.build(text)

# 存储到 MySQL
mysql_client.save_graph(graph_data=graph, source_file="test.txt")
```

#### 批量生成

```python
from backend.tasks import batch_build_knowledge_graphs

# 批量生成知识图谱
batch_build_knowledge_graphs(directory="data/raw", file_pattern="*.txt")
```

### 2. 智能问答

```bash
# 使用 curl 测试智能问答
curl -X POST "http://localhost:5001/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "胰腺炎有什么症状？", "max_results": 5}'
```

### 3. RAG 检索

```python
from rag.rag_pipeline import RAGPipeline
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient

# 初始化组件
neo4j_client = Neo4jClient()
llm_client = LLMClient()
embedding_client = EmbeddingClient()

# 初始化 RAG 流水线
rag_pipeline = RAGPipeline(neo4j_client, llm_client, embedding_client)

# 执行 RAG 查询
result = rag_pipeline.query("胰腺炎的治疗方法有哪些？")
print(result["answer"])
```

## API 文档

### 1. 健康检查

```
GET /health
```

**返回示例**：
```json
{
  "status": "healthy",
  "database": "connected",
  "entity_extractor": true,
  "rag_enabled": true
}
```

### 2. 统计查询

```
GET /stats
```

**返回示例**：
```json
{
  "entities": {
    "Disease": 150,
    "Symptom": 480,
    "Drug": 320,
    "Department": 50
  },
  "relationships": {
    "HAS_SYMPTOM": 1200,
    "TREATS": 850,
    "BELONGS_TO": 150
  },
  "total_entities": 1000,
  "total_relationships": 2200
}
```

### 3. 实体搜索

```
GET /search?entity_type=Disease&keyword=胰腺&limit=10
```

**返回示例**：
```json
[
  {
    "name": "胰腺炎",
    "type": "Disease",
    "description": "胰腺因胰蛋白酶的自身消化作用而引起的疾病"
  }
]
```

### 4. 智能问答

```
POST /query
```

**请求体**：
```json
{
  "question": "胰腺炎有什么症状？",
  "max_results": 5
}
```

**返回示例**：
```json
{
  "question": "胰腺炎有什么症状？",
  "answer": "**胰腺炎** 的主要症状包括：\n\n• 腹痛\n• 恶心\n• 呕吐\n• 发热\n• 黄疸",
  "sources": [{"type": "Disease", "name": "胰腺炎"}],
  "query_type": "symptom"
}
```

### 5. 数据导入

```
POST /api/import
```

**请求体**：
```json
{
  "entities": [
    {
      "name": "测试疾病",
      "type": "Disease",
      "properties": {"description": "这是一个测试疾病"}
    }
  ],
  "relationships": [
    {
      "source": "测试疾病",
      "target": "测试症状",
      "type": "HAS_SYMPTOM"
    }
  ]
}
```

**返回示例**：
```json
{
  "status": "success",
  "message": "数据导入完成",
  "stats": {
    "entities_created": 1,
    "relationships_created": 1
  }
}
```

## Hadoop 处理流程

### 1. 文本提取（PDF → 文本）

```bash
# Hadoop MapReduce 作业
python hadoop/mapreduce/pdf_extract/mapper.py input.pdf | python hadoop/mapreduce/pdf_extract/reducer.py
```

### 2. 文本清理

```bash
# 清理特殊字符、空格等
python hadoop/mapreduce/text_clean/mapper.py input.txt
```

### 3. 文本分块

```bash
# 将文本分成 1000 字符/段落
python hadoop/mapreduce/text_chunk/mapper.py input.txt
```

## Celery 任务管理

### 1. 启动 Celery 服务

```bash
# 启动 Celery  worker
celery -A backend.celery_app worker --loglevel=info

# 启动 Celery Beat（定时任务）
celery -A backend.celery_app beat --loglevel=info
```

### 2. 常用任务

| 任务名称 | 功能 |
|---------|------|
| `batch_build_knowledge_graphs` | 批量生成知识图谱 |
| `process_file` | 处理单个文件 |
| `upload_to_hdfs` | 上传文件到 HDFS |
| `process_hdfs_file` | 处理 HDFS 上的文件 |

## RAG 工作机制

### 1. 查询解析

- 意图识别
- 实体提取
- 关键词提取

### 2. 信息检索

- 图检索：基于 Neo4j 的关系查询
- 向量检索：基于文本嵌入的相似度匹配
- 混合检索：结合图检索和向量检索的结果

### 3. 上下文构建

- 根据查询意图组织上下文
- 限制上下文长度
- 排序和去重

### 4. 答案生成

- 基于 LLM 的答案生成
- 引用来源信息
- 计算置信度

## 测试和开发

### 1. 运行单元测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_simple_kg.py -v
```

### 2. 功能测试

```bash
# 测试知识图谱生成
python tests/test_simple_kg.py

# 测试 RAG 流水线
python tests/test_rag_pipeline.py

# 测试 API
python tests/test_api.py
```

### 3. 诊断和调试

```bash
# 检查数据库连接
python scripts/check_mysql_graphs.py

# 检查实体标签
python scripts/check_node_labels.py

# 检查 Hadoop 环境
python scripts/check_hadoop_env.py
```

## 部署方案

### 1. 本地开发环境

```
┌───────────────────────────────────────────────────┐
│  本地主机                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ API服务 │  │ Celery  │  │ Neo4j   │  │ MySQL   │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
└───────────────────────────────────────────────────┘
```

### 2. 云服务器部署

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                  云服务器                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Nginx   │  │ API服务 │  │ Celery  │  │ Hadoop  │  │ Neo4j   │  │ MySQL   │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

## 项目成果和意义

### 1. 已实现功能

- ✅ 知识图谱生成：支持从多种数据源生成医学知识图谱
- ✅ 智能问答：基于知识图谱和 LLM 的智能问答系统
- ✅ RAG 检索：融合图检索、向量检索和混合检索的 RAG 流水线
- ✅ 分布式处理：基于 Hadoop 的分布式文本处理
- ✅ 异步任务管理：基于 Celery 的异步任务队列
- ✅ 多数据库支持：Neo4j + MySQL 数据持久化
- ✅ RESTful API：完整的 API 服务
- ✅ Docker 容器化：全系统容器化部署

### 2. 技术创新

- **融合检索**：结合图检索和向量检索的混合检索策略
- **分布式处理**：基于 Hadoop 的大规模文本处理
- **异步架构**：Celery 异步任务管理，支持高并发
- **多数据库协同**：Neo4j 图数据库 + MySQL 关系型数据库

### 3. 应用价值

- 医学知识管理：结构化存储和管理医学知识
- 智能辅助诊断：为医生提供辅助诊断支持
- 医学教育：为学生提供交互式学习工具
- 医疗决策支持：为医疗决策提供数据支持

## 未来计划

- [ ] 优化实体-关系提取算法，提高准确率
- [ ] 支持更多医学数据源（如 XML、CSV 等）
- [ ] 增强 RAG 流水线，支持多模态数据
- [ ] 开发 Web 前端界面，提高用户体验
- [ ] 支持更多 LLM 模型，提高灵活性
- [ ] 优化分布式处理性能，支持更大规模数据

## 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

- 项目维护者：[您的姓名/团队名称]
- 邮箱：[您的邮箱地址]
- GitHub：[项目 GitHub 地址]

## 致谢

感谢所有为这个项目做出贡献的开发者和研究者！

---

**项目状态**：活跃开发中
**最后更新**：2026-01-08
**版本**：v2.0.0