# 医疗知识图谱系统 - 后端服务

> 基于 **Neo4j 图数据库 + MySQL + 检索增强生成（RAG）+ FastAPI** 的医疗知识图谱问答系统。  
> 支持疾病—症状—治疗—科室—并发症等医学知识的结构化存储、智能问答与可视化。

---

## 📑 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [运行环境](#运行环境)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [快速启动](#快速启动)
- [API 说明](#api-说明)
- [数据导入方式](#数据导入方式)
  - [1. 纯文本 / 目录导入](#1-纯文本--目录导入)
  - [2. JSON 医疗数据导入](#2-json-医疗数据导入)
  - [3. PDF 医学文献导入（带清洗）](#3-pdf-医学文献导入带清洗)
- [RAG 工作机制](#rag-工作机制)
- [测试与诊断](#测试与诊断)
- [注意事项 & 已知限制](#注意事项--已知限制)
- [TODO / 未来扩展](#todo--未来扩展)

---

## 📖 项目简介

本项目是一个**医疗知识图谱 + 智能问答系统**，主要功能包括：

- **智能问答**：基于知识图谱的自然语言问答，支持疾病症状、治疗方法、就诊科室等查询
- **知识图谱构建**：从文本、JSON、PDF 等格式自动构建医疗知识图谱
- **实体搜索**：支持多类型医疗实体的模糊搜索和精确匹配
- **图谱可视化**：提供知识图谱的可视化数据接口
- **历史记录**：完整记录用户操作历史，支持查询和管理
- **文件上传**：支持多种格式的医疗文档上传和处理

核心设计思路：

1. 用 **MySQL** 作为主存储，在 `knowledge_graphs` 表的 `graph_data` JSON 字段中存储完整的知识图谱数据（节点和关系）
2. 用 **Neo4j** 作为可视化缓存，用于快速的可视化展示和查询
3. 用 **LLM（DeepSeek）** 对医学文本进行实体关系抽取，自动构建知识图谱
4. 用 **图检索 + 规则意图识别** 处理结构化问题（例如"什么症状、怎么治疗、看什么科"等）
5. 在图谱答案不足时，**可选** 调用 RAG 流水线综合图谱与文本信息生成回答
6. **图谱隔离与切换**：每个上传的文件生成独立的图谱，支持通过 `graph_id` 切换查看不同的图谱

---

## 🧩 系统架构

```text
           ┌──────────────────────────┐
           │        FastAPI API        │
           │  /api/upload /api/query   │
           │  /api/kg/* /api/search    │
           └────────────┬─────────────┘
                        │
            ┌───────────┴───────────┐
            │   实体提取 + 意图识别   │
            │   EntityExtractor      │
            └───────────┬───────────┘
                        │
     ┌──────────────────┴──────────────────┐
     │             查询处理                │
     │  症状/治疗/科室/病因/药物 专用查询  │
     │  （图查询优先，其次 RAG，最后兜底） │
     └──────────────────┬──────────────────┘
                        │
               ┌────────┴────────┐
               │   RAGPipeline    │  ← 可选
               │  (LLM + 检索)    │
               └────────┬────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
   ┌────┴────┐                   ┌─────┴─────┐
   │ Neo4j   │                   │  MySQL   │
   │ 图数据库 │                   │ 业务数据库 │
   └─────────┘                   └──────────┘
```

### ⭐ 核心功能模块

#### 1. 医疗知识图谱（Neo4j）

**实体类型包括：**
- Disease（疾病）
- Symptom（症状）
- Treatment（治疗）
- Medicine/Drug（药物）
- Examination（检查）
- Department（科室）
- Complication（并发症）
- RiskFactor（风险因素）

**关系类型包括：**
- HAS_SYMPTOM（有症状）
- TREATED_BY（通过治疗）
- USES_MEDICINE（使用药物）
- REQUIRES_EXAM（需要检查）
- BELONGS_TO（属于科室）
- CAUSES（导致）
- LEADS_TO（导致）
- ASSOCIATED_WITH（关联）
- INCREASES_RISK（增加风险）

`scripts/init_database.py` 会为每个实体类型创建唯一约束，并构建全文索引。

#### 2. 业务数据存储（MySQL）

**主要数据表：**
- `history_records` - 历史记录表（上传、查询、构建任务等）
- `knowledge_graphs` - 知识图谱元数据表（包含 `graph_data` JSON 字段，存储完整的节点和关系数据）
- `uploaded_files` - 上传文件信息表

**数据存储策略：**
- **MySQL 作为主存储**：所有知识图谱的完整数据（节点和关系）存储在 `knowledge_graphs` 表的 `graph_data` JSON 字段中
- **Neo4j 作为可视化缓存**：用于快速的可视化展示和查询
- **数据同步机制**：系统优先从 Neo4j 读取数据，如果 Neo4j 为空，则从 MySQL 读取并自动同步到 Neo4j
- **图谱隔离**：每个上传的文件生成独立的图谱，支持通过 `graph_id` 切换查看不同的图谱

#### 3. 图检索（GraphRetriever）

基于疾病/症状等实体，从 Neo4j 中进行多跳检索。

**支持查询类型：**
- 疾病 → 症状列表
- 疾病 → 用药 / 治疗措施
- 疾病 → 就诊科室
- 症状 → 可能疾病
- 药物 → 针对疾病

#### 4. 意图识别 + 实体抽取

由 `rag/query_parser.py` 中的 QueryParser 实现：

- 启动时从 Neo4j 加载所有 Disease / Symptom / Drug 名称到内存
- 在用户问题中用"最长匹配"方式抽取疾病/症状/药物实体
- 用正则模式识别意图：
  - "什么症状 / 有哪些症状 / 临床表现" → 症状查询
  - "怎么治疗 / 用什么药" → 治疗查询
  - "看什么科 / 挂哪个科" → 科室查询
  - "某症状可能是什么病" → 病因查询
  - "某药有什么作用 / 治疗什么病" → 药物查询

#### 5. RAG（Retrieval-Augmented Generation，可选）

在规则 & 图查询无法找到合适答案时，降级调用 RAGPipeline：

- **图检索（GraphRetriever）**：从 Neo4j 中检索结构化知识（主要方式）
- **向量检索（VectorRetriever）**：使用 `BAAI/bge-large-zh-v1.5` Embedding 模型进行语义检索（已接入真实模型）
- **混合检索策略**：可配置图检索和向量检索的权重，实现最佳检索效果
- **LLM 生成**：使用 DeepSeek Chat 作为生成模型，综合检索结果生成回答
- **当前推荐**：系统主打"图谱 + 规则问答"，RAG 作为补充能力，支持混合检索策略

---

## 🖥️ 运行环境

| 组件 | 要求 / 说明 |
|------|------------|
| Python | ≥ 3.9 |
| Neo4j | 4.x / 5.x（本地或 Aura 均可） |
| MySQL | 5.7+ / 8.0+ |
| FastAPI | 0.104.1+ |
| Uvicorn | 0.24.0+ |
| DeepSeek | 需要可用的 API Key |
| Embedding | **已接入真实模型**：`BAAI/bge-large-zh-v1.5`（本地模型，需安装 `sentence-transformers`）<br>首次运行会自动下载模型（约 1.3GB），需要网络连接和充足磁盘空间 |
| 系统平台 | Windows / Linux / macOS 均可 |

---

## 📁 项目结构

```
knowledge_gragh/
│  run.py                   # 应用启动入口
│  api_server.py            # RAG 查询接口服务
│  config.py                # 全局配置（Neo4j / LLM / RAG / 日志等）
│  .env                     # 环境变量配置
│  requirements.txt          # Python 依赖
│  README.md                # 本文档
│
├─backend/                  # 主应用模块
│    app.py                 # FastAPI 主服务（文件上传、知识图谱构建等）
│    config.py              # Backend 配置（可选）
│    mysql_client.py        # MySQL 客户端（可选，推荐使用 db/mysql_client.py）
│
├─api/                      # API 模块
│    main.py                # RAG 查询接口（与 api_server.py 功能类似）
│
├─scripts/                  # 工具脚本集合
│    init_database.py      # 创建索引 + 约束 + 导入初始知识
│    import_data.py         # 文本/JSON/目录导入（通用版本）
│    import_medical_data.py # 医疗 JSON 数据导入
│    import_pdf.py          # PDF 医学文献导入（带清洗）
│
├─db/                       # 数据库客户端
│    neo4j_client.py        # Neo4j 客户端封装（连接 / 读写 / 统计）
│    mysql_client.py         # MySQL 客户端封装（SQLAlchemy）
│
├─llm/                      # LLM 模块
│    client.py              # DeepSeek LLM 客户端封装（健康检查 / 调用）
│
├─rag/                      # RAG 模块
│    rag_pipeline.py        # 检索增强生成管线
│    query_parser.py        # 查询解析器（意图/实体/关键词）
│    graph_retriever.py     # 图检索器（GraphRetriever）
│
├─kg/                       # 知识图谱构建
│    builder.py             # KnowledgeGraphBuilder（从文本构建图谱）
│
├─tests/                    # 测试文件
│    test_system.py         # 系统级测试
│    test_api.py            # API 测试
│    test_app.py            # 应用测试
│    diagnose_search.py     # 搜索诊断工具
│    check_table.py         # 数据库表检查工具
│    ...                    # 其他测试文件
│
├─MYSQL/                    # MySQL 相关文件
│    init_mysql.sql         # MySQL 数据库初始化脚本
│    init_mysql_db.py       # MySQL 初始化 Python 脚本
│    test_sql_import.sql    # SQL 导入测试脚本
│    MYSQL_INTEGRATION.md   # MySQL 集成文档
│    MYSQL_PASSWORD_RESET.md # MySQL 密码重置指南
│
├─docs/                     # 文档
│    API.md                 # API 接口文档
│    ARCHITECTURE.md        # 架构文档
│    DEPLOYMENT.md          # 部署文档
│
└─data/                     # 数据文件
     raw/                   # 原始数据（txt / pdf / json 等）
     processed/             # 处理后数据
     examples/              # 示例数据
```

---

## ⚙️ 配置说明

所有配置由 `config.py` 统一管理，并从 `.env` 读取：

### 示例 .env（请按实际环境调整）

```env
# 应用配置
DEBUG=True
HOST=0.0.0.0
PORT=5001
ENVIRONMENT=development
LOG_LEVEL=INFO

# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=knowledge_graph

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TEMPERATURE=0.7

# Embedding 模型配置（已接入真实模型）
USE_LOCAL_EMBEDDING=True  # 使用本地模型（推荐），False 则使用 API 或占位向量
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5  # 本地模型名称（首次运行会自动下载）
EMBEDDING_DIM=1024  # 向量维度（BAAI/bge-large-zh-v1.5 为 1024 维）

# 可选：API 方式（如果 USE_LOCAL_EMBEDDING=False）
# OPENAI_API_KEY=your-api-key  # OpenAI 兼容 API Key
# OPENAI_BASE_URL=https://api.openai.com/v1  # API 地址
# OPENAI_EMBEDDING_MODEL=text-embedding-ada-002  # API 模型名称

# RAG 配置
VECTOR_TOP_K=5
MAX_GRAPH_DEPTH=3
# 推荐在仅使用图检索时：
# VECTOR_WEIGHT=0.0
# GRAPH_WEIGHT=1.0
```

⚠️ **若 NEO4J_PASSWORD 或 DEEPSEEK_API_KEY 未配置，config.py 会给出明确错误/警告。**

---

## 🚀 快速启动

### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

**⚠️ 重要提示：Embedding 模型安装与下载**

本项目已接入真实的 Embedding 模型 `BAAI/bge-large-zh-v1.5`，需要安装以下依赖：

**必需依赖：**
- `sentence-transformers`（已包含在 `requirements.txt` 中）
- `torch`（PyTorch，`sentence-transformers` 会自动安装）
- `transformers`（HuggingFace Transformers 库）

**首次运行时的模型下载：**

首次运行时会自动从 HuggingFace 下载 Embedding 模型（`BAAI/bge-large-zh-v1.5`，约 1.3GB），请确保：
- ✅ 网络连接正常（需要访问 `https://huggingface.co`）
- ✅ 磁盘空间充足（至少 2GB 可用空间，模型会缓存到 `~/.cache/huggingface/`）
- ✅ 如果下载较慢，可以考虑：
  - 使用 HuggingFace 镜像源（设置环境变量 `HF_ENDPOINT=https://hf-mirror.com`）
  - 或手动下载模型到本地缓存目录

**验证 Embedding 模型安装：**

安装完成后，运行以下命令测试 Embedding 模型是否正常工作：

```bash
# 测试 Embedding 模型加载和功能
python tests/test_embedding.py

# 检查 Embedding 环境（诊断工具）
python scripts/check_embedding_env.py
```

如果测试通过，你会看到：
- ✅ 模型成功加载
- ✅ 向量维度：1024
- ✅ 相似度计算正常（相似文本相似度高，不相关文本相似度低）

**常见问题：**

1. **`ModuleNotFoundError: No module named 'sentence_transformers'`**
   - 解决：`pip install sentence-transformers`

2. **`ImportError: cannot import name 'cached_download'`**
   - 解决：升级 `sentence-transformers`：`pip install sentence-transformers --upgrade`

3. **PyCharm 中使用不同的 Python 解释器**
   - 解决：确保 PyCharm 的 Python 解释器与终端使用的解释器一致（参考 `PYCHARM_SETUP.md`）

4. **Windows 终端编码错误（`UnicodeEncodeError`）**
   - 解决：已在代码中修复，使用 ASCII 字符替代 Unicode 符号

### 2️⃣ 配置 .env

将上述示例 `.env` 放到项目根目录，并填入你自己的 Neo4j 密码、MySQL 密码与 DeepSeek Key。

### 3️⃣ 初始化数据库

#### 初始化 Neo4j

```bash
python scripts/init_database.py
```

它会自动：
- 检查并显示当前配置摘要
- 创建实体唯一约束与全文索引
- 使用 KnowledgeGraphBuilder 导入一段基础知识文本
- 在日志中输出 Neo4j 节点数、关系数、标签数、关系类型数

#### 初始化 MySQL

```bash
# 使用 SQL 脚本
mysql -u root -p < MYSQL/init_mysql.sql

# 或使用 Python 脚本
python MYSQL/init_mysql_db.py
```

### 4️⃣ 启动 API 服务

#### 方式一：使用 run.py（推荐）

```bash
python run.py
```

`run.py` 会自动检测并启动合适的应用：
- 优先使用 `backend/app.py`（包含完整业务功能）
- 或使用 `api/main.py`（RAG 查询接口）

#### 方式二：直接启动特定服务

```bash
# 启动主应用（文件上传、知识图谱构建等）
uvicorn backend.app:app --host 0.0.0.0 --port 5001

# 或启动 RAG 查询接口
python api_server.py
```

**默认访问地址：**
- 根路径：http://localhost:5001/
- 文档（Swagger UI）：http://localhost:5001/docs
- ReDoc：http://localhost:5001/redoc

**启动时会：**
- 连接 Neo4j 和 MySQL
- 加载 Embedding 模型（如果 `USE_LOCAL_EMBEDDING=True`，首次运行会下载模型）
- 通过 QueryParser 从数据库加载所有疾病/症状/药物实体
- 初始化 RAGPipeline（如果配置允许）

---

## 🔌 API 说明

### 主应用接口（backend/app.py）

#### 文件上传
- **POST** `/api/upload` - 上传文件（支持 TXT、PDF、JSON 等格式）

#### 知识图谱构建
- **POST** `/api/kg/build` - 从上传的文件生成知识图谱（异步）
- **GET** `/api/kg/list` - 获取已生成的知识图谱列表
- **GET** `/api/kg/{graph_id}` - 获取知识图谱详情
- **GET** `/api/kg/{graph_id}/visualize` - 获取知识图谱可视化数据
- **GET** `/api/kg/{graph_id}/nodes` - 获取知识图谱节点列表
- **GET** `/api/kg/{graph_id}/relations` - 获取知识图谱关系列表

#### 知识图谱查询
- **GET** `/api/graph/data` - 获取图谱数据（用于可视化）
  - 支持 `graph_id` 参数：指定图谱ID，返回该图谱的数据
  - 不指定 `graph_id`：返回全部图谱的合并数据
  - 支持 `limit` 和 `offset` 参数：用于分页
- **GET** `/api/graph/list` - 获取知识图谱列表（用于图谱切换功能）
- **GET** `/api/graph/entity/{entity_id}` - 获取实体详情
- **GET** `/api/graph/relation/{relation_id}` - 获取关系详情
- **GET** `/api/graph/entity/{entity_id}/expand` - 扩展实体（获取关联实体）

#### 实体搜索
- **GET** `/api/search/entities` - 搜索实体（支持类型筛选和关键词搜索）
- **GET** `/api/graph/entities/search` - 图谱实体搜索（旧版接口）
- **GET** `/api/graph/relations/search` - 搜索关系

#### 历史记录
- **GET** `/api/history/list` - 获取历史记录列表（支持类型和状态筛选）
- **GET** `/api/history/stats` - 获取历史记录统计信息
- **POST** `/api/history/save` - 保存历史记录
- **GET** `/api/history/search` - 搜索历史记录

### RAG 查询接口（api/main.py / api_server.py）

#### 系统接口
- **GET** `/` - 返回服务状态、版本等基本信息
- **GET** `/health` - 健康检查，验证 Neo4j 连接及组件状态
- **GET** `/api/stats` - 返回知识图谱统计信息

#### 智能问答
- **POST** `/api/query` - 智能问答入口

**请求体示例：**
```json
{
  "question": "急性胰腺炎有什么典型症状？",
  "use_graph": true,
  "use_vector": true,
  "top_k": 5
}
```

**内部处理顺序：**
1. 实体提取 + 意图识别（QueryParser）
2. 若识别为：
   - 症状查询 → 调 `query_disease_symptoms`
   - 治疗查询 → 调 `query_disease_treatment`
   - 科室查询 → 调 `query_disease_department`
   - 病因查询（由症状出发） → 调 `query_symptom_diseases`
   - 药物查询 → 调 `query_drug_info`
3. 若以上规则不能处理，并且 RAGPipeline 可用：
   - 调用 `RAGPipeline.answer(...)`，返回自然语言回答
4. 若 RAG 也不可用 / 失败，则返回提示用户如何提问的 fallback

#### 实体搜索（旧版）
- **GET** `/api/search` - 搜索实体（支持 entity_type 和 keyword 参数）

#### 知识管理
- **POST** `/api/entity` - 创建实体
- **POST** `/api/relation` - 创建关系
- **POST** `/api/knowledge/import` - 导入知识文本

#### 图谱可视化
- **GET** `/api/graph/data` - 获取图谱可视化数据
- **GET** `/api/entities/{entity_type}` - 获取指定类型的实体列表

---

## 📥 数据导入方式

### 1. 纯文本 / 目录导入

使用 `scripts/import_data.py` 中的 `DataImporter`：

**支持功能：**
- 从单个 `.txt` 文件导入：
  - 按固定长度切分为多个片段
  - 每段调用 `KnowledgeGraphBuilder.process_text` 构建图谱
- 从目录批量导入：扫描 `*.txt` 和 `*.json` 文件逐个导入

**使用示例：**
```bash
python scripts/import_data.py "data/raw/sample.txt"
python scripts/import_data.py "data/raw/"  # 批量导入目录
```

### 2. JSON 医疗数据导入

使用 `scripts/import_medical_data.py` 中的 `MedicalDataImporter`：

**JSON 格式示例：**
```json
{
  "diseases": [
    {
      "name": "急性胰腺炎",
      "category": "消化系统",
      "description": "...",
      "department": "消化内科"
    }
  ],
  "symptoms": [
    {
      "name": "上腹部疼痛",
      "severity": "重",
      "description": "..."
    }
  ],
  "drugs": [
    {
      "name": "某抗生素",
      "type": "抗菌药",
      "usage": "...",
      "dosage": "...",
      "treats": ["急性胰腺炎"]
    }
  ],
  "departments": [
    {
      "name": "消化内科",
      "description": "..."
    }
  ]
}
```

**导入逻辑包括：**
- 导入疾病、症状、药物、科室节点
- 创建：
  - 疾病-症状：`(Disease)-[:HAS_SYMPTOM]->(Symptom)`
  - 药物-疾病：`(Drug)-[:TREATS]->(Disease)`
  - 疾病-科室：`(Disease)-[:BELONGS_TO]->(Department)`

⚠️ **注意：** `import_from_json(..., clear_existing=True)` 会清空现有数据库，请谨慎使用。

### 3. PDF 医学文献导入（带清洗）

使用 `scripts/import_pdf.py`：

```bash
python scripts/import_pdf.py "data/raw/某篇医学论文.pdf"
```

**流程：**
1. 用 `pdfplumber` 逐页提取文本
2. 对文本做医学场景清洗（仅保留与疾病/症状/治疗等相关的正文）：
   - 截断 "参考文献 / References / 致谢" 之后的所有内容
   - 去掉图表标题、页眉页脚、页码、纯数字/公式行
   - 去掉 `[1]` / `[2-5]` 这类文献标号
   - 去掉 `(Smith 2020)` 等作者-年份引用
   - 去掉 URL / 邮箱
3. 将清洗后的文本按 chunk（默认约 1000 字）分段
4. 使用 `KnowledgeGraphBuilder.process_text` 逐段构建知识图谱
5. 在终端输出：
   - 分段总数、成功处理段数
   - 新增实体数、新增关系数
   - 出错段数

**典型导入规模示例：**
- 原始文本长度约 12000 字
- 切分为 13 个 chunk
- 新增实体约 170 个
- 新增关系约 160 条
- 出错段数为 0

**数据存储流程：**
1. 文件上传后，系统开始异步处理
2. 处理过程中，实体和关系被写入 Neo4j（用于实时可视化）
3. 处理完成后，系统收集该文件生成的所有节点和关系
4. 将完整的图谱数据保存到 MySQL 的 `knowledge_graphs` 表的 `graph_data` JSON 字段中
5. 每个文件生成独立的图谱，通过 `graph_id` 可以区分和切换

---

## 📚 示例：从一篇 PDF 到可查询知识图谱

下面用一个真实的场景，走一遍完整流程：  
**从一篇"急性胰腺炎相关医学论文 / 指南 PDF" → 导入 Neo4j → 用 API 进行问答。**

### 1️⃣ 准备 PDF 文件

1. 找一篇与你关注领域相关的医学 PDF，比如：
   - 急性胰腺炎的急诊救治新进展
   - 某疾病的诊治指南
   - 某疾病的健康科普手册

2. 将文件放到项目的 `data/raw/` 目录下

### 2️⃣ 使用 import_pdf.py 导入 PDF

```bash
# Windows 示例（注意路径用双引号包起来）
python scripts/import_pdf.py "data/raw/急性胰腺炎的急诊救治新进展.pdf"
```

### 3️⃣ 在 Neo4j 中验证导入结果

打开 Neo4j Browser，执行下面几条查询：

**查看整体规模变化：**
```cypher
MATCH (n) RETURN count(n) AS node_count;
MATCH ()-[r]->() RETURN count(r) AS relationship_count;
```

**按疾病名称检查节点：**
```cypher
MATCH (d:Disease)
WHERE d.name CONTAINS "胰腺炎"
RETURN d
LIMIT 10;
```

**查看疾病相关的关系：**
```cypher
MATCH (d:Disease)-[r]->(x)
WHERE d.name CONTAINS "胰腺炎"
RETURN d, type(r) AS rel_type, x
LIMIT 20;
```

### 4️⃣ 使用 API /api/query 进行问答

确保服务已经启动，然后通过 Swagger UI 或其他工具调用 `/api/query` 接口：

**示例问题 1：疾病症状**
```json
POST http://localhost:5001/api/query
Content-Type: application/json

{
  "question": "急性胰腺炎有哪些典型症状？",
  "use_graph": true,
  "top_k": 5
}
```

**示例问题 2：治疗方式**
```json
{
  "question": "急性胰腺炎一般如何治疗？",
  "use_graph": true,
  "top_k": 5
}
```

通过以上步骤，你就完成了一个完整链路：  
**一篇医学 PDF → 清洗抽取 → 写入知识图谱 → 通过 API 进行结构化医学问答。**

---

## 🧠 RAG 工作机制

本项目以 **"图谱优先"** 为核心设计，RAG 作为可选增强能力。

**RAGPipeline 的典型调用方式：**

1. **解析查询：**
   - 使用 `QueryParser` 从自然语言问题中抽取意图、实体、关键词等

2. **图检索（GraphRetriever）：**
   - 从 Neo4j 中检索与关键实体相关的节点和关系
   - 这是主要的检索方式，能够准确获取结构化知识

3. **向量检索（VectorRetriever）：**
   - **已接入真实 Embedding 模型**：使用 `BAAI/bge-large-zh-v1.5` 对文本片段进行编码
   - 将用户查询转换为 1024 维向量，基于余弦相似度检索相关文本片段
   - 支持混合检索策略：可配置 `VECTOR_WEIGHT` 和 `GRAPH_WEIGHT` 来平衡图检索和向量检索的权重
   - 向量检索能够捕获语义相似性，补充图检索可能遗漏的信息

4. **LLM 生成回答：**
   - 将检索到的结构化信息（图检索结果）和文本片段（向量检索结果）作为上下文
   - 调用 DeepSeek Chat 生成最终回答
   - 返回 `answer + sources + confidence` 信息

**检索策略配置：**

在 `.env` 文件中可以配置检索权重：
- `VECTOR_WEIGHT=0.0, GRAPH_WEIGHT=1.0`：仅使用图检索（推荐用于结构化查询）
- `VECTOR_WEIGHT=0.3, GRAPH_WEIGHT=0.7`：混合检索（图检索为主，向量检索为辅）
- `VECTOR_WEIGHT=0.5, GRAPH_WEIGHT=0.5`：平衡检索（图检索和向量检索并重）

---

## 🧪 测试与诊断

### 1. 系统级测试：`tests/test_system.py`

依次测试七个部分：
- Neo4j 连接与统计信息
- LLM 连接健康
- Embedding 客户端
- 查询解析器（QueryParser）
- 图检索器（GraphRetriever）
- RAG 流水线
- 端到端问答（多条医疗相关问题）

**运行：**
```bash
python tests/test_system.py
```

### 2. API 测试：`tests/test_api.py`

测试 API 接口功能。

**运行：**
```bash
python tests/test_api.py
```

### 3. 应用测试：`tests/test_app.py`

测试主应用功能。

**运行：**
```bash
python tests/test_app.py
```

### 4. 搜索诊断：`tests/diagnose_search.py`

专门用于诊断 Neo4j 中疾病搜索行为：
- 查看前若干疾病/症状节点
- 测试 CONTAINS 模糊匹配
- 测试正则匹配
- 测试精确匹配

可在你导入新数据后，用它来确认搜索逻辑是否符合预期。

### 5. Embedding 模型测试：`tests/test_embedding.py`

专门用于测试 Embedding 模型的加载和功能：
- 检查模型是否成功加载
- 测试文本编码功能
- 测试批量编码功能
- 验证相似度计算（相似文本 vs 不相关文本）

**运行：**
```bash
python tests/test_embedding.py
```

### 6. Embedding 环境诊断：`scripts/check_embedding_env.py`

诊断 Embedding 模型的环境配置问题：
- 检查 Python 环境
- 检查依赖包安装情况（`sentence-transformers`, `torch`, `transformers` 等）
- 尝试加载模型并报告错误
- 检查配置文件

**运行：**
```bash
python scripts/check_embedding_env.py
```

### 7. 数据库表检查：`tests/check_table.py`

检查 MySQL 数据库表结构和数据。

### 8. 数据持久化测试：`tests/test_data_persistence.py`

测试数据是否正确保存到 MySQL 的 `graph_data` 字段：
- 验证所有图谱是否都有 `graph_data`
- 验证 `graph_data` 格式是否正确（nodes 和 edges）
- 验证数据一致性（MySQL vs API）

**运行：**
```bash
python tests/test_data_persistence.py
```

### 9. MySQL 到 Neo4j 同步测试：`tests/test_mysql_neo4j_sync.py`

测试 MySQL 到 Neo4j 的数据同步功能：
- 从 MySQL 读取 `graph_data`
- 将数据同步到 Neo4j
- 验证同步后的数据是否正确

**运行：**
```bash
python tests/test_mysql_neo4j_sync.py
```

### 10. 图谱切换功能测试：`tests/test_graph_switch.py`

测试图谱切换功能：
- 获取图谱列表
- 测试按 `graph_id` 获取特定图谱数据
- 验证数据隔离（不同图谱的数据不混淆）

**运行：**
```bash
python tests/test_graph_switch.py
```

### 11. 端到端集成测试：`tests/test_end_to_end.py`

测试完整的工作流程：
- 后端服务连接
- 获取图谱列表和数据
- 图谱切换功能
- 实体搜索功能
- 智能问答功能
- 统计接口

**运行：**
```bash
python tests/test_end_to_end.py
```

---

## ⚠️ 注意事项 & 已知限制

### Embedding 模型已接入真实模型

✅ **已接入真实 Embedding 模型**：`BAAI/bge-large-zh-v1.5`

- 系统默认使用本地 Embedding 模型（`USE_LOCAL_EMBEDDING=True`）
- 如果模型加载失败，系统会降级到 API 方式或占位向量，并在日志中提示
- 推荐使用本地模型以获得更好的性能和稳定性
- 向量检索已完全可用，支持与图检索的混合检索策略

### FastAPI 生命周期管理

`api/main.py` 已使用新的 `lifespan` API，消除了弃用警告。  
`api_server.py` 仍使用旧的 `on_event`，但不影响使用。

### 医学语义的正确性

图谱关系的正确性取决于 LLM 的抽取质量和原始文献的可靠性；  
对于关键医疗结论，仍建议由专业医生审核，不应直接用于临床决策。

### PDF 文本质量依赖文档本身格式

扫描版、双栏排版、复杂表格会影响 PDF 文本解析质量；  
清洗规则尽量通用，但在少数文献上可能需要进一步微调。

### 多个 FastAPI 应用入口

当前项目包含多个 FastAPI 应用：
- `backend/app.py` - 主应用（文件上传、知识图谱构建等业务功能）
- `api/main.py` - RAG 查询接口（使用新的 lifespan API）
- `api_server.py` - RAG 查询接口（旧版）

建议统一使用 `run.py` 启动，它会自动选择合适应用。

---

## 📝 TODO / 未来扩展

- [x] 统一 FastAPI 应用入口，整合所有接口到一个应用（`backend/app.py`）
- [x] 接入真实的 Embedding 模型（BAAI/bge-large-zh-v1.5），并设计混合检索策略（Graph + Vector）
- [x] 完善前端集成，提供完整的 Web 界面（包含图谱切换、智能问答、可视化等功能）
- [x] 实现知识图谱数据持久化（MySQL 主存储 + Neo4j 可视化缓存）
- [x] 实现图谱切换功能（支持查看不同文件生成的独立图谱）
- [ ] 为 PDF 导入增加更智能的章节识别（如只抽取 "诊断 / 治疗 / 预后 / 推荐"等部分）
- [ ] 更丰富的医学领域扩展：从胰腺炎扩展到消化系统、重症医学等
- [ ] 添加用户认证和权限管理
- [ ] 优化知识图谱构建性能，支持大规模数据导入
- [ ] 添加知识图谱版本管理和回滚功能

---

## 🙌 致谢

本项目最初以 **胰腺炎知识图谱** 为实验场景，逐步演化为一个可扩展的医疗知识图谱 RAG 框架。  
欢迎在此基础上扩展更多疾病、添加更多数据源、接入更强大的模型与检索方式。

如需二次开发或部署到生产环境，请根据自身需求完善安全审查和医学内容审核流程。

---

**最后更新**：2025年1月  
**版本**：v1.0.0
