# 大规模医学知识图谱生成与智能问答系统

## 项目简介

本项目是一个功能完整的大规模医学知识图谱生成与智能问答系统，基于 Docker、Hadoop 和 Celery 构建，实现了从 PDF/文本数据到知识图谱的全流程自动化。**智能问答已由简单 RAG 检索升级为 Agent 级架构**：通过 LangGraph 编排 LLM 与多种工具（图谱检索、文献检索等），支持多轮对话、指代消解与流式输出。

### 核心功能

✅ **知识图谱生成**：支持从 PDF、纯文本、JSON 等多种数据源生成医学知识图谱
✅ **Agent 智能问答**：基于 LangGraph 的 Agent 架构，LLM 自主调用 RAG 工具（图检索、向量检索、混合检索），支持多轮对话与 session 记忆
✅ **RAG 作为工具**：原 RAG 流水线封装为 Agent 可调用的工具，融合图检索、向量检索与文献检索，由 Agent 决策何时调用、如何组合
✅ **分布式处理**：基于 Hadoop 的分布式文本处理，支持大规模数据
✅ **异步任务管理**：基于 Celery 的异步任务队列，支持批量任务处理
✅ **多数据库支持**：Neo4j 图数据库 + MySQL 关系型数据库，实现数据持久化
✅ **RESTful API**：完整的 API 服务，支持知识图谱查询、认证（注册/登录）、历史记录（分页与最多 1000 条）、图谱按 graph_id 查询、文档知识库（Chroma）等
✅ **历史记录**：统一存储问答、图谱查询、图谱构建、上传等记录；支持列表（type/status/limit/offset）、保存、状态更新、搜索；删除（单条/批量/清空）接口计划补充
✅ **Docker 容器化**：全系统容器化，支持快速部署和环境一致性

## 文档与测试

- **文档**：`docs/` 目录（API.md、ARCHITECTURE.md、DEPLOYMENT.md），集中存放接口与架构说明
- **脚本**：`scripts/` 目录，含环境检查（Hadoop、MySQL、Agent、知识库等）、**前后端 API 对接检查**（`check_frontend_backend_api.py`）、手动测试脚本（批量构建示例等），详见 [scripts/README.md](scripts/README.md)
- **自动化测试**：`tests/` 目录，运行 `pytest tests/`，详见 [tests/README.md](tests/README.md)
- **前后端联调**：后端默认通过 `python run.py` 启动并监听 5001；先执行 `python scripts/check_frontend_backend_api.py` 确认 19 项接口通过，再按前端项目 `docs/FRONTEND_E2E_TEST_CHECKLIST.md` 做手工端到端测试

## 云上演示模式（低配服务器）

> 适用于 2 核 2G 等轻量云主机，用最少资源在公网展示系统界面和基础功能。

- **推荐部署方式**：使用 `docker-compose.cloud-minimal.yml` 仅启动 **backend + MySQL + Redis + Neo4j**，前端通过 `npm run build` 生成 `dist/` 后交给云主机上的 **Nginx** 托管（详见 `docs/DEPLOYMENT_CLOUD_STEP4.md` 与 `docs/DEPLOYMENT_FRONTEND_STEP8.md`）。
- **适合在云上演示的功能**：登录 / 注册、知识图谱浏览与搜索、历史记录、上传入口与页面流转等——即「看得见、点得动」的主要业务流程。
- **不推荐在 2G 机器上长期开启的功能**：Agent 问答（`/api/agent/query` / `/api/agent/query/stream`）及大规模离线构建，这些链路会同时占用 LLM、Neo4j、MySQL 等资源，在 2G 内存下容易导致整机卡死。
- **建议做法**：在本地或更高配环境演示「问答 + 大规模构建」效果；云主机上以「演示模式」为主，必要时可以暂时去掉 `.env` 中的 `DEEPSEEK_API_KEY`，让后端快速返回「服务不可用」的提示，由前端给出友好文案。

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
│  │  │ 健康检查│  │ 统计查询│  │ 实体搜索│  │ Agent问答│  │ 数据导入│   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                业务逻辑层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    知识图谱生成  │  │  Agent（LangGraph）│  │  RAG 工具（图/文献）│  │ 任务管理 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    实体提取器    │  │  LLM + bind_tools │  │  图检索/向量检索  │  │ 会话记忆 │   │
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
│  │    Neo4j 图数据库  │  │    MySQL 关系数据库  │  │  Chroma 向量库   │  │ 本地存储 │   │
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
| 向量库 | Chroma | 文档知识库存储与检索 |
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
  1. 数据导入（`POST /api/upload` 或 Hadoop 批量上传到 HDFS）
  2. 正文提取（PDF 用 pdfplumber，TXT/JSON 直接读入）
  3. 文本分块与基于 LLM 的实体-关系提取（`kg.builder`）
  4. 写入 Neo4j，并将图谱元数据与 graph_data（节点/边）写入 MySQL `knowledge_graphs`
  5. 单文件构建：`POST /api/kg/build` 异步执行；批量构建：Hadoop 集成接口使用已提取文本并行调用 `build_single_file_kg`，不跑真实 Hadoop MR

### 2. Agent 智能问答（由 RAG 升级为 Agent 架构）

**核心功能**：基于 **LangGraph Agent** 的智能问答，替代原有「固定 RAG 流水线」，由 LLM 自主决定是否调用工具、调用哪些工具以及如何组合结果。

- **架构升级**：
  - **原方案**：用户问题 → 固定 RAG 流水线（解析 → 检索 → 上下文 → 生成）→ 答案
  - **现方案**：用户问题 → **Agent（LLM + 工具绑定）** → 可选多轮：LLM 决定调用「图检索」「文献检索」等工具 → 工具返回结果 → LLM 综合生成答案；支持多轮对话与 session 记忆，便于指代、追问

- **技术实现**：
  - **状态图**：LangGraph `StateGraph`，状态为 `messages`（含多轮对话）
  - **节点**：`agent`（LLM + `bind_tools`）、`tools`（执行图检索、文献检索等 RAG 工具）
  - **边**：`START → agent`；若 LLM 发出 `tool_calls` 则 `agent → tools → agent`，否则 `agent → END`
  - **输出**：最终 AI 回复 `answer`、来源 `sources`（来自图谱/来自文献）

- **RAG 作为工具**：原 RAG 能力封装为 Agent 可调用的工具（如图谱检索、文档检索），由 Agent 在推理过程中按需调用，检索策略仍包含：
  - 图检索（基于 Neo4j）
  - 向量/文献检索（基于嵌入与知识库）
  - 混合检索（图+文献）
  - 关键词检索（备用）

- **接口**：`POST /api/agent/query`（非流式）、`POST /api/agent/query/stream`（SSE 流式）；可选 `session_id` 做多轮记忆；前端 Chat 已对接上述接口。

### 3. API 服务

**核心功能**：完整的 RESTful API 服务，与 Vue 前端联调对接（主入口为 `backend.app`，通过 `python run.py` 启动）

- **认证**：`POST /api/auth/register`、`POST /api/auth/login`（MySQL users 表，SHA256 密码）
- **智能问答**：`POST /api/agent/query`（非流式）、`POST /api/agent/query/stream`（SSE 流式）；可选 `session_id`、`deep_think`；`POST /api/query` 为传统 RAG 兼容接口
- **图谱**：`GET /api/graph/list`、`GET /api/graph/data`（支持 `graph_id`，不传则合并当前用户全部图谱；数据来自 MySQL `knowledge_graphs.graph_data`）；`GET /api/kg/list`、`GET /api/kg/{graph_id}/visualize` 等；**说明**：前端「清除图谱」调用的 `DELETE /api/graph/clear` 当前未实现，计划补充
- **实体搜索**：`GET /api/search/entities`（优先 Neo4j，回退 MySQL 图谱节点）
- **历史记录**：`GET /api/history/list`（type、status、limit 默认 1000、offset）、`POST /api/history/save`、`PUT /api/history/{history_id}/status`、`GET /api/history/search`；单条/批量删除与清空接口计划补充
- **文件与构建**：`POST /api/upload`、`POST /api/kg/build`（单文件异步构建）、`GET /api/kg/build/progress/{task_id}`；Hadoop 集成见 `backend.hadoop_api`（批量上传 HDFS、批量构建任务状态）
- **文档知识库**：`GET/POST/PATCH /api/kb/bases`、`POST /api/kb/documents/ingest`、`GET /api/kb/documents/search`、`GET /api/kb/documents/list`、`DELETE /api/kb/documents/{doc_id}`、`POST /api/kb/documents/reindex`（Chroma 向量库，支持多知识库与 user_id 过滤）
- **数据模板**：`GET /api/templates/{template_type}`（disease、symptom、medicine、relation）

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

# 2. 启动数据库服务（按需）
docker-compose up -d neo4j mysql

# 3. 启动 API 服务（推荐：统一入口，默认监听 5001）
python run.py
# 或：python api_server.py

# 4. 启动 Celery 服务（批量任务需用时）
celery -A backend.celery_app worker --loglevel=info
```

前端联调时，将前端 `.env.development` 中 `VUE_APP_API_BASE_URL` 指向 `http://localhost:5001`，并先运行 `python scripts/check_frontend_backend_api.py` 做接口检查。

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

### 2. Agent 智能问答（推荐）

```bash
# 使用 curl 测试 Agent 问答（非流式）
curl -X POST "http://localhost:5001/api/agent/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "胰腺炎有什么症状？"}'

# 多轮对话（可选 session_id）
curl -X POST "http://localhost:5001/api/agent/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "它怎么治疗？", "session_id": "your-session-id"}'
```

Agent 内部会按需调用 RAG 工具（图检索、文献检索等）并综合生成答案；流式接口为 `POST /api/agent/query/stream`，前端 Chat 已对接。

### 3. RAG 流水线（作为 Agent 工具底层）

若需单独使用 RAG 能力（不经过 Agent），可仍使用原有 RAG 模块；当前默认问答路径为 Agent 调用 RAG 工具：

```python
from rag.rag_pipeline import RAGPipeline
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient

# 初始化 RAG 流水线（Agent 内工具会复用类似能力）
rag_pipeline = RAGPipeline(neo4j_client, llm_client, embedding_client)
result = rag_pipeline.query("胰腺炎的治疗方法有哪些？")
print(result["answer"])
```

## API 文档

完整接口以实际挂载为准；启动 `python run.py` 后可通过 **OpenAPI `/docs`** 查看所有路由。以下为常用接口摘要。

### 1. Agent 智能问答（推荐）

```
POST /api/agent/query
POST /api/agent/query/stream   # SSE 流式
```

**请求体**：
```json
{
  "question": "胰腺炎有什么症状？",
  "session_id": "可选，多轮对话会话 id",
  "deep_think": false
}
```

**返回示例**（非流式）：
```json
{
  "question": "胰腺炎有什么症状？",
  "answer": "胰腺炎的主要症状包括腹痛、恶心、呕吐、发热、黄疸等...",
  "sources": [{"type": "graph", "name": "胰腺炎"}, {"type": "doc", "name": "文献片段"}],
  "response": "...",
  "processing_time": 1.23
}
```

Agent 内部通过 LangGraph 编排 LLM 与 RAG 工具（图检索、文献检索），自动完成检索与综合回答；流式接口返回 SSE，便于前端打字机效果。

### 2. 其他常用接口摘要

- **认证**：`POST /api/auth/register`、`POST /api/auth/login`
- **图谱**：`GET /api/graph/list`、`GET /api/graph/data?graph_id=...`（数据来自 MySQL）
- **实体搜索**：`GET /api/search/entities?keyword=...&type=...&limit=...`
- **历史**：`GET /api/history/list`、`POST /api/history/save`、`PUT /api/history/{id}/status`
- **上传与构建**：`POST /api/upload`、`POST /api/kg/build`、`GET /api/kg/build/progress/{task_id}`
- **知识库**：`GET/POST /api/kb/bases`、`POST /api/kb/documents/ingest`、`GET /api/kb/documents/search`、`GET /api/kb/documents/list`
- **模板**：`GET /api/templates/{template_type}`（disease、symptom、medicine、relation）

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

## Agent 与 RAG 工具机制

智能问答已升级为 **Agent 架构**：由 LangGraph 编排「LLM + 工具」，RAG 作为工具被 Agent 按需调用。

### 1. Agent 流程（当前默认问答路径）

1. **用户提问** → 可选带入 `session_id` 的历史消息，拼成 `messages`
2. **Agent 节点**：LLM（DeepSeek 等）`bind_tools`（图检索、文献检索等），根据当前 `messages` 决定是否发起 `tool_calls`
3. **Tools 节点**：执行图检索、向量/文献检索等，返回结构化结果（如实体、关系、文献片段）
4. **循环**：工具结果追加为 `ToolMessage` → 再次进入 Agent 节点，直至 LLM 不再调用工具，输出最终回复
5. **输出**：`answer`、`sources`（来自图谱/来自文献），可选写回 session 供多轮使用

### 2. RAG 工具（检索策略）

- **图检索**：基于 Neo4j 的关系与实体查询
- **向量/文献检索**：基于文本嵌入与知识库文档
- **混合检索**：图 + 文献结果合并
- **关键词检索**：备用方案

上述能力封装为 Agent 可调用的工具，由 LLM 在推理中决定调用哪些、如何组合，而非固定流水线顺序。

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
# 前后端 API 对接检查（联调前建议先跑）
python scripts/check_frontend_backend_api.py

# 检查数据库连接
python scripts/check_mysql_graphs.py

# 检查实体标签
python scripts/check_node_labels.py

# 检查 Hadoop 环境
python scripts/check_hadoop_env.py
```

更多脚本说明见 [scripts/README.md](scripts/README.md)，测试用例说明见 [tests/README.md](tests/README.md)。

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
- ✅ **Agent 智能问答**：由简单 RAG 升级为 LangGraph Agent，LLM 自主调用 RAG 工具（图检索、文献检索），支持多轮对话与流式输出
- ✅ RAG 作为工具：图检索、向量检索、混合检索封装为 Agent 工具，由 Agent 按需调用
- ✅ 分布式处理：基于 Hadoop 的分布式文本处理
- ✅ 异步任务管理：基于 Celery 的异步任务队列
- ✅ 多数据库支持：Neo4j + MySQL 数据持久化
- ✅ RESTful API：完整的 API 服务，与 Vue 前端联调（图谱、历史记录、知识库、模板下载等）
- ✅ 历史记录：统一存储与状态更新，支持分页与最多 1000 条，图谱构建/上传状态正确回显
- ✅ Docker 容器化：全系统容器化部署

### 2. 技术创新

- **Agent 架构**：LangGraph 编排 LLM 与 RAG 工具，替代固定 RAG 流水线，支持多轮与指代
- **融合检索**：图检索与向量/文献检索作为 Agent 工具，由 LLM 决策调用与组合
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
- [ ] 增强 Agent 工具（如多模态、更多检索源）
- [x] 与 Vue 前端联调（历史记录、图谱构建、知识库、模板下载等已对接）
- [ ] 补充历史记录删除接口（单条/批量/清空）与图谱清空接口（`DELETE /api/graph/clear`），与前端对齐
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