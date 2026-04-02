# 智护银龄·忆路康：老龄认知障碍人群低认知负荷知识辅助系统

## 项目简介

本项目是一个面向老龄认知障碍人群的多模态认知负荷量化评估与低认知负荷知识辅助系统。系统基于知识图谱与大模型，实现从 PDF/文本到知识图谱的全流程构建，并通过基于 LangGraph 的 Agent 架构进行智能问答。同时，系统集成行为分析、NASA-TLX主观问卷与EEG生理信号（预留）三大模态，实现认知负荷的多维度量化评估。

### 核心功能

✅ **知识图谱生成**：支持从 PDF、纯文本、JSON 等多种数据源生成医学知识图谱
✅ **Agent 智能问答**：基于 LangGraph 的 Agent 架构，LLM 自主调用 RAG 工具（图检索、向量检索、混合检索），支持多轮对话与 session 记忆
✅ **RAG 作为工具**：原 RAG 流水线封装为 Agent 可调用的工具，融合图检索、向量检索与文献检索，由 Agent 决策何时调用、如何组合
✅ **多模态认知负荷评估**：行为埋点 + NASA-TLX主观问卷 + **EEG支持（模拟器+真实硬件）**，多模态加权融合量化认知负荷
✅ **NASA-TLX问卷评估**：简化版NASA-TLX六维度评分（脑力/体力/时间需求、绩效、努力、挫败感），适老化设计
✅ **行为分析评分**：基于点击/回退/错误/耗时等行为特征的实时认知负荷评估
✅ **EEG硬件支持**：预留Muse/OpenBCI/Emotiv等主流设备接口，**已实现Muse S模拟器和真实硬件对接**，支持个体基线校准
✅ **融合评估报告**：单次评估报告 + 趋势分析报告 + 周期汇总报告，多维度雷达图与个性化建议  
✅ **分布式处理**：基于 Hadoop 的分布式文本处理，支持大规模数据  
✅ **异步任务管理**：基于 Celery 的异步任务队列，支持批量任务处理  
✅ **多数据库支持**：Neo4j 图数据库 + MySQL 关系型数据库，实现数据持久化  
✅ **RESTful API**：完整的 API 服务，支持知识图谱查询、认证（注册/登录）、历史记录（分页与最多 1000 条）、图谱按 graph_id 查询、文档知识库（Chroma）等  
✅ **历史记录**：统一存储问答、图谱查询、图谱构建、上传等记录；支持列表（type/status/limit/offset）、保存、状态更新、搜索；删除（单条/批量/清空）接口已补全  
✅ **Docker 容器化**：全系统容器化，支持快速部署和环境一致性
✅ **认知负荷评估闭环**：行为埋点 + NASA-TLX问卷 → 前端趋势图/雷达图报告 → MySQL持久化
✅ **机构看板（P3）**：管理员/医生可查看跨用户聚合统计（事件、任务、问卷、活跃趋势、来源对比）
✅ **适老角色支持（elderly）**：角色更新接口支持 `elderly`，前端可切换到“老人简化模式”与适老主题

### 最近更新（智能体 & 多模态）

- **EEG硬件支持完整实现**：新增 `eeg_collector.py`（Muse S数据采集）、`eeg_hardware_scorer.py`（Muse S评分器）、`eeg_simulator.py`（开发测试模拟器）、`modes.py`（运行模式配置）；支持模拟器模式和真实Muse S硬件模式切换
- **多模态认知负荷评估**：新增认知负荷评估模块 `backend/cognitive/`，集成行为分析、NASA-TLX问卷、EEG预留接口，支持多模态加权融合评估
- **NASA-TLX问卷评估**：简化版NASA-TLX六维度评分（脑力/体力/时间需求、绩效、努力、挫败感），1-7分滑动评分，适老化设计
- **行为分析评分器**：基于点击/回退/错误/耗时等行为特征的实时认知负荷评估，支持回退率、错误率、完成率等指标
- **融合评估报告**：单次评估报告 + 趋势分析报告 + 周期汇总报告，多维度雷达图、个性化建议、风险预警
- **患者教育生成**：新增 `intent=patient_education` 智能体能力，后端提供结构化患者教育内容（标题 + 分节 + 温馨提示），前端专门页面与排版展示，支持一键生成「给患者看的说明书」。
- **科普推文生成**：新增 `intent=science_tweet`，可将普通问答结果概括为 1～3 条科普推文，并返回推荐话题标签，前端聊天中支持「推文版」按钮。
- **多模态工具**：后端新增语音转写（STT）、图片 OCR + 影像解读等多模态接口，作为 Agent 工具与上传/聊天入口使用。
- **语音输入（Whisper + FFmpeg）**：前端 Chat 页面支持语音输入，后端使用本地 OpenAI Whisper 模型进行中文转写，并通过 `.env` 中的 `FFMPEG_BIN_DIR` 自动配置 ffmpeg 可执行路径。
- **图文结合问答**：智能体问答结果与图谱/文献来源统一管理，返回 `sources` 与可视化数据，前端右侧以「来自图谱 / 来自文献」等形式展示，实现回答 + 可视图谱/文献的图文效果。
- **多 LLM 模型适配**：新增统一的 `llm/models_config.py`，支持 DeepSeek、OpenAI GPT、Gemini、通义千问、豆包、智谱 GLM、文心一言、Kimi、Grok 等主流模型；前端聊天界面可切换模型，未配置的模型会提示「未配置该模型」。

### 最近更新（PDF 与图谱构建优化）

- **PDF 增强提取**：`backend/pdf_extract.py` 统一 PDF 正文 + 表格（pdfplumber `extract_tables()` 转文本）+ 扫描页 OCR（PaddleOCR，页图由 PyMuPDF 渲染）；环境变量 `PDF_EXTRACT_ENABLE_OCR`、`PDF_EXTRACT_MIN_TEXT_PER_PAGE` 可配置。单文件上传、批量上传、入库提取均走该逻辑后再 `clean_medical_text`。
- **图谱构建 Prompt 与后处理**：`kg/builder.py` 中实体关系提取增加 few-shot 示例与输出约束（subject/object 必须来自 entities）；`temperature=0` 提高可复现性；后处理校验与规范化（`_validate_and_normalize_extraction`）：实体名规范化与同义合并、实体/关系类型映射、关系缺实体时丢弃并打日志。
- **批量构建与 Hadoop 折中方案**：默认仍为「上传时本地提取 + 多线程并行构建」，不依赖 Hadoop。仅当请求中 `use_hadoop=true` 且存在「未在本地做提取」的文件时，对该部分文件走 MapReduce（提取→清洗→分块），从 HDFS 拉回 text_clean 结果并写回 `uploaded_files`，再用同一套并行构建。前端数据上传页可勾选「对缺文本文件使用 MapReduce」，任务完成后展示「本次构建：已使用 MapReduce 预处理」或「仅使用本地已提取文本」。
- **启动与日志**：ChromaDB 遥测关闭并静默相关日志；requests 与 urllib3/chardet 版本警告已抑制（`run.py`、`backend/app.py`）。

### 企业级加固与工程化（近期）

- **安全**：密码 bcrypt 加密、CORS 可配置、JWT 生产环境校验、登录限流（slowapi）
- **稳定性**：优雅关闭（MySQL/Neo4j 连接释放）、生产环境日志脱敏
- **测试**：pytest 规范用例（conftest、test_health、test_auth_api）、pytest-cov 覆盖率
- **部署**：前端 Docker 化（Nginx 托管 + /api 反代）、环境变量统一（config、mysql_client）
- **文档**：架构图（ARCHITECTURE.md）、部署文档、演示脚本（DEMO_SCRIPT.md）
- **配置**：.env.example 完善、前端生产构建优化（sourceMap 关闭、splitChunks）

## 文档与测试

- **文档**：`docs/` 目录（API.md、ARCHITECTURE.md、DEPLOYMENT.md、DEMO_SCRIPT.md、**HYBRID_RAG_DESIGN.md**、**OPTIMIZATION_SUGGESTIONS.md**），集中存放接口、架构、部署、演示、Hybrid RAG 设计与优化建议（含批量构建与 MapReduce 现状与折中方案说明）
- **脚本**：`scripts/` 目录，含环境检查（Hadoop、MySQL、Agent、知识库等）、**前后端 API 对接检查**（`check_frontend_backend_api.py`）、手动测试脚本（批量构建示例等），详见 [scripts/README.md](scripts/README.md)
- **自动化测试**：`tests/` 目录，运行 `pytest tests/`（含 conftest、test_health、test_auth_api 等），支持 `--cov=backend` 覆盖率，详见 [tests/README.md](tests/README.md)
- **前后端联调**：后端默认通过 `python run.py` 启动并监听 5001；先执行 `python scripts/check_frontend_backend_api.py` 确认 19 项接口通过，再按前端项目 `docs/FRONTEND_E2E_TEST_CHECKLIST.md` 做手工端到端测试

## 前后端联调

### 1）启动后端（FastAPI，默认 5001）

```bash
pip install -r requirements.txt
python run.py
```

### 2）启动前端（Vue，端口以终端输出为准）

在前端仓库根目录 `.env.development` 配置：

```bash
VUE_APP_API_BASE_URL=http://localhost:5001
```

然后运行：

```bash
npm install
npm run serve
```

### 3）推荐演示链路（5 分钟）

- 老人角色切换：`/profile` → 角色选择 **老人（简化模式）** → 自动启用适老主题与四入口导航
- 服药提醒：`/medication` → 生成今日任务 → 确认服用 → 触发问卷
- 学知识：`/patient-education` → 生成内容（支持自适应模式）→ 完成 → 触发问卷
- 认知负荷评估：`/cognitive-load` → 趋势图 + 波动报告 → 上传到服务器
- 家属周报：`/family-report` → 一页式周度汇总与建议
- 机构看板（管理员/医生）：`/admin/dashboard` → 跨用户统计与图表


## 云上演示模式（低配服务器）

> 适用于 2 核 2G 等轻量云主机，用最少资源在公网展示系统界面和基础功能。

- **推荐部署方式**：使用 `docker-compose.cloud-minimal.yml` 仅启动 **backend + MySQL + Redis + Neo4j**，前端通过 `npm run build` 生成 `dist/` 后交给云主机上的 **Nginx** 托管；或使用 `docker-compose up -d` 一键启动含 **frontend** 的完整栈（详见 `docs/DEPLOYMENT.md`、`docs/DEPLOYMENT_CLOUD_STEP4.md` 与 `docs/DEPLOYMENT_FRONTEND_STEP8.md`）。
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
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │  │ 健康检查│   │ 统计查询│   │ 实体搜索│  │ Agent问答│  │ 数据导入│  │认知评估│   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
│  └───────────────────────────────────────────────────────────────────┘   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                业务逻辑层                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    知识图谱生成  │  │  Agent（LangGraph）││RAG 工具（图/文献│   │ 任务管理 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │    实体提取器    │  │ LLM + bind_tools│  │  图检索/向量检索 │  │ 会话记忆 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │  认知负荷评估    │  │ NASA-TLX评分器  │  │ 行为/EEG评分器  │               │
│  │  (多模态融合)   │  │                 │  │                 │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                数据处理层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐ │
│  │ Hadoop 分布式处理│  │Celery 异步任务   │  │  PDF 提取处理    │  │ 文本处理│  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │   │
│  │    文本清理      │  │    文本分块      │  │    实体关系提取  │             │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │   │
└───────┬───────────────────────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│                                数据存储层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────┐   │
│  │  Neo4j 图数据库  │  │MySQL 关系数据库  │  │ Chroma 向量库   │  │ 本地存储 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

## 核心技术栈

| 技术类别 | 核心技术 | 版本/说明 |
|---------|---------|-----------|
| 容器化 | Docker | 20.10+ |
| 分布式处理 | Hadoop | 3.3.0+ |
| 异步任务 | Celery | 5.3+ |
| 图数据库 | Neo4j | 5.x（当前测试版本 5.15） |
| 关系数据库 | MySQL | 8.0+ |
| 向量库 | Chroma | 文档知识库存储与检索 |
| API 框架 | FastAPI | 0.100+ |
| 编程语言 | Python | 3.8+ |
| LLM | DeepSeek API | - |
| 向量嵌入 | BAAI/bge-large-zh-v1.5 | - |
| 知识图谱构建 | 自定义算法 | 基于 LLM 的实体关系提取 |
| 认知负荷评估 | 多模态融合 | NASA-TLX + 行为分析 + **EEG支持** |
| 评估量表 | NASA-TLX | 简化版六维度认知负荷量表 |
| 生理信号 | **EEG（Muse S）** | **已实现模拟器+硬件采集**，支持MuseLSL协议 |

## 产品定位

智护银龄·忆路康的产品定位，可以概括为：**面向老龄认知障碍人群及照护者的低认知负荷知识辅助与患者教育系统**。与商业计划书中的整体思路一一对应，主要体现在：

- **知识装饰（多形态呈现）**：同一份医学/照护内容，可以在前端以「长文 / 分步 / 卡片」等多种形式展示，并支持配图与朗读，便于根据老人当下状态与偏好选择合适信息量与呈现方式。
- **认知负荷评估（行为 + 主观 + 预留生理）**：系统在关键路径上记录行为数据（如任务起止时间、分步点击次数、回退行为等），并在阅读/问答结束后弹出简易主观问卷；数据采用「时间戳 + 事件类型 + 关键参数」结构存储，未来可与 EEG、眼动等生理信号按时间轴对齐，用于多模态认知负荷研究。
- **场景聚焦（服药 / 复诊 / 日常照护）**：问答与患者教育优先覆盖服药提醒、复诊准备、日常安全（防跌倒、防走失）、记忆/病情简述、家属沟通要点等高频认知照护场景，并在图谱构建与检索里对「认知障碍、照护、服药、记忆」等关键词做偏置，使默认结果更贴近照护实践。
- **适老化设计**：提供适老主题（放大字号、提高对比度）、分步展开阅读（一次只展示一小段或一步）、一键朗读等能力，减少单屏信息量和操作负担；界面导航也围绕「问一问、患者教育、知识图谱」等 2–3 个主入口展开，降低选择负担。

本 README 中的功能模块说明、架构设计与评测脚本，均以上述产品定位为约束：一方面保证医学知识与图谱/检索的严谨性，另一方面在前后端实现中尽量降低老年用户与照护者的认知负荷，体现「低认知负荷知识辅助」这一核心价值。

## 功能模块详细说明
### 1. 知识图谱生成

**核心功能**：从多种数据源生成医学知识图谱

- **支持的数据源**：
  - PDF 文档（本地增强提取：正文 + 表格 + 扫描页 OCR，见 `backend/pdf_extract.py`；可选经 Hadoop MapReduce 预处理）
  - 纯文本文件
  - JSON 格式数据
  - 批量数据处理

- **生成流程**：
  1. 数据导入（`POST /api/upload` 或 `POST /api/hadoop/upload/batch` 批量上传，上传时即做本地 PDF 增强提取并写入 `pdf_text`）
  2. 正文提取（PDF 用 `backend.pdf_extract.extract_pdf_text`：正文 + 表格 + 疑似扫描页 OCR；TXT/JSON 直接读入）→ 统一 `clean_medical_text` 清洗
  3. 文本分块与基于 LLM 的实体-关系提取（`kg.builder`，含 few-shot 与后处理校验）
  4. 写入 Neo4j，并将图谱元数据与 graph_data 写入 MySQL `knowledge_graphs`
  5. 单文件构建：`POST /api/kg/build` 异步执行；批量构建：`POST /api/hadoop/build/batch` 默认使用已提取的 `pdf_text` 并行构建；若 `use_hadoop=true` 且部分文件无本地 `pdf_text`，则对该部分走 MapReduce 再拉回后同一套并行构建

### 2. Agent 智能问答

**核心功能**：基于 **LangGraph Agent** 的智能问答，替代原有「固定 RAG 流水线」，由 LLM 自主决定是否调用工具、调用哪些工具以及如何组合结果。

- **架构升级**：
  - **原方案**：用户问题 → 固定 RAG 流水线（解析 → 检索 → 上下文 → 生成）→ 答案
  - **现方案**：用户问题 → **Agent（LLM + 工具绑定）** → 可选多轮：LLM 决定调用「图检索」「文献检索」等工具 → 工具返回结果 → LLM 综合生成答案；支持多轮对话与 session 记忆，便于指代、追问

- **技术实现**：
  - **状态图**：LangGraph `StateGraph`，状态为 `messages`（含多轮对话）
  - **节点**：`agent`（LLM + `bind_tools`）、`tools`（执行图检索、文献检索等 RAG 工具）
  - **边**：`START → agent`；若 LLM 发出 `tool_calls` 则 `agent → tools → agent`，否则 `agent → END`
  - **输出**：最终 AI 回复 `answer`、来源 `sources`（来自图谱/来自文献）

- **RAG 作为工具**：原 RAG 能力封装为 Agent 可调用的工具（如图谱检索、文档检索），由 Agent 在推理过程中按需调用，检索策略包含：
  - 图检索（基于 Neo4j）
  - 向量/文献检索（基于 Chroma 嵌入与知识库）
  - **Hybrid RAG 混合检索**（图 + Chroma 文档 + 关键词，RRF 融合）
  - 关键词检索（备用）

- **接口**：`POST /api/agent/query`（非流式）、`POST /api/agent/query/stream`（SSE 流式）；可选 `session_id` 做多轮记忆；前端 Chat 已对接上述接口。

### 3. API 服务

**核心功能**：完整的 RESTful API 服务，与 Vue 前端联调对接（主入口为 `backend.app`，通过 `python run.py` 启动）

- **认证**：`POST /api/auth/register`、`POST /api/auth/login`（MySQL users 表，bcrypt 密码）
- **智能问答**：`POST /api/agent/query`（非流式）、`POST /api/agent/query/stream`（SSE 流式）；可选 `session_id`、`deep_think`；`POST /api/query` 为传统 RAG 兼容接口
- **图谱**：`GET /api/graph/list`、`GET /api/graph/data`（支持 `graph_id`，不传则合并当前用户全部图谱；数据来自 MySQL `knowledge_graphs.graph_data`）；`GET /api/kg/list`、`GET /api/kg/{graph_id}/visualize` 等；
- **实体搜索**：`GET /api/search/entities`（优先 Neo4j，回退 MySQL 图谱节点）
- **历史记录**：`GET /api/history/list`（type、status、limit 默认 1000、offset）、`POST /api/history/save`、`PUT /api/history/{history_id}/status`、`GET /api/history/search`；
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

# 5. （可选，多模态语音输入）安装并测试 ffmpeg
# Windows 上推荐从 gyan.dev 下载 ffmpeg-*-essentials_build，解压后在 .env 中配置 FFMPEG_BIN_DIR 为 bin 目录：
#   FFMPEG_BIN_DIR=F:\ffmpeg\ffmpeg-2026-02-23-git-xxxx-essentials_build\bin
# 然后重新启动后端服务。
```

前端联调时，将前端 `.env.development` 中 `VUE_APP_API_BASE_URL` 指向 `http://localhost:5001`，并先运行 `python scripts/check_frontend_backend_api.py` 做接口检查。

## 认知负荷评估（接口说明）

> 系统支持多模态认知负荷量化评估，集成行为分析、NASA-TLX问卷与EEG信号。

### 核心评估接口

- `POST /api/cognitive-load/assess`：多模态认知负荷评估（支持行为事件+NASA-TLX问卷，自动融合评分）
- `GET /api/cognitive-load/modalities`：查询当前可用评估模态
- `GET /api/cognitive-load/assessment/{id}`：获取单条评估记录
- `GET /api/cognitive-load/history`：获取用户评估历史

### EEG接口（模拟器+硬件）

系统支持两种EEG模式：开发测试用的**模拟器模式**和真实Muse S设备的**硬件模式**。

#### 模拟器模式API

```bash
# 启用模拟器（默认中等负荷）
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/simulate/enable?cognitive_level=medium"

# 生成模拟EEG特征
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/simulate/features?cognitive_level=high"

# 创建模拟个体基线
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/simulate/baseline"

# 完整模拟评估（带基线）
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/simulate/assess?cognitive_level=high&with_baseline=true"

# 禁用模拟器
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/simulate/disable"
```

#### 硬件模式API（Muse S）

```bash
# 连接Muse S设备（需先在Muse Direct应用中启用LSL Streaming）
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/hardware/connect?timeout=10"

# 创建个体基线（60秒安静闭眼）
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/hardware/baseline?duration=60"

# 采集并评分（30秒）
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/hardware/collect?duration=30"

# 获取硬件状态
curl -X GET "http://localhost:5001/api/cognitive-load/eeg/hardware/status"

# 断开设备并切换回模拟器模式
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/hardware/disconnect"

# 手动切换模式
curl -X POST "http://localhost:5001/api/cognitive-load/eeg/switch-mode?mode=simulation"
```

#### EEG评分算法

| 指标 | 说明 | 负荷高时 |
|------|------|---------|
| Theta/Beta比率 | θ/β | ↑ |
| Theta功率 | 相对基线 | ↑ |
| Alpha功率 | 相对基线 | ↓ |

### 报告接口

- `GET /api/cognitive-load/report/single/{id}`：单次评估报告（含雷达图、关键发现、建议）
- `GET /api/cognitive-load/report/trend`：趋势分析报告（支持days参数，默认7天）
- `GET /api/cognitive-load/report/period`：周期汇总报告
- `GET /api/cognitive-load/trend/analysis`：趋势数据查询
- `GET /api/cognitive-load/stats/user`：用户认知负荷统计

### 旧版接口（兼容）

- `POST /api/cognitive-load/events`：批量上传行为事件
- `POST /api/cognitive-load/questionnaires`：批量上传问卷
- `GET /api/admin/cognitive-dashboard`：机构看板聚合统计（仅 `admin/doctor`）

### 评估报告预览

评估报告包含：综合评分圆环、NASA-TLX六维度雷达图、行为与问卷分项评分、风险预警、关键发现、个性化建议、趋势图表。

技术方案文档：`docs/技术方案.md`
模块代码：`backend/cognitive/`

### 认知负荷评估快速测试

#### 1. 启动后端
```bash
python run.py
```

#### 2. API测试

```bash
# 测试评估接口（不保存到数据库）
curl -X POST "http://localhost:5001/api/cognitive-load/assess?save=false" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test_user" \
  -d '{
    "user_id": "test_user",
    "task_id": "test_task",
    "source": "patient_education",
    "behavior_events": [{"event_type": "click", "ts": 1000, "params": {}}],
    "nasa_tlx_answers": {
      "mental_demand": 4,
      "physical_demand": 3,
      "temporal_demand": 2,
      "performance": 5,
      "effort": 3,
      "frustration": 2
    }
  }'

# 获取评估报告
curl "http://localhost:5001/api/cognitive-load/report/trend?days=7" \
  -H "X-User-Id: test_user"
```

#### 3. 单元测试
```bash
# pytest测试（20个测试用例）
python -m pytest tests/test_cognitive_pytest.py -v

# 自定义测试框架（23个测试用例）
python tests/test_cognitive_load.py
```

## 本地 Embedding / 镜像常见问题（CPU 环境）

- **首次加载慢**：`BAAI/bge-large-zh-v1.5` 在 CPU 上首次加载可能较慢；已在启动时尝试预加载（见 `run.py`）。
- **hf-mirror 解析失败**：如遇 `Failed to resolve hf-mirror.com`，建议在 `.env` 设置：

```bash
HF_ENDPOINT=https://huggingface.co
```

或临时关闭本地 embedding（以便快速演示）：

```bash
USE_LOCAL_EMBEDDING=False
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

若需单独使用 RAG 能力（不经过 Agent），可仍使用原有 RAG 模块；当前默认问答路径为 Agent 调用 RAG 工具。

**启用 Hybrid RAG**（图+Chroma+关键词 RRF 融合）：

```python
from backend.query_service import run_query

# 通过 run_query 启用混合检索
result = run_query(
    question="胰腺炎有哪些症状和并发症？",
    use_hybrid=True,
    user_id="当前用户ID",  # 用于 Chroma 文档过滤
    max_results=10,
)
```

或直接使用 RAGPipeline：`pipeline.answer(query, use_hybrid=True, user_id="xxx")`。

### 4. 语音输入（STT）与前端使用

后端通过 `backend.stt_service.transcribe` + `backend.multimodal_router.api_stt_transcribe` 提供语音转文本能力，前端 Chat 页面使用麦克风按钮调用：

- **依赖准备**
  - Python 依赖：`openai-whisper` 已在 `requirements.txt` 中声明；
  - 系统依赖：本机需安装 `ffmpeg`，并在 `.env` 中配置：
    ```env
    FFMPEG_BIN_DIR=路径到\ffmpeg\bin
    ```
  - `backend/stt_service.py` 会在每次调用时读取 `FFMPEG_BIN_DIR` 并把该目录加入当前进程的 `PATH`，避免环境变量未生效导致 `WinError 2`。

- **调用流程**
  - 前端使用 `MediaRecorder` 录音，录制结束后通过 `/api/stt/transcribe` 上传音频（默认使用 webm）；
  - 后端将音频写入临时文件，使用本地 Whisper 模型（默认 `base`，CPU 下 `fp16=False`）进行中文转写；
  - 返回识别出的文本，前端将其自动填入问答输入框，可继续发送给 Agent。

> 注意：前端问答与患者教育功能已增加登录校验——页面可以匿名访问，但发送消息、语音输入、图片解读、生成/保存患者教育等操作会检测登录状态，未登录时会提示并跳转到 `/login`。

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

- **批量构建默认不跑 MapReduce**：当前批量构建以「上传时本地提取」的 `pdf_text` + 多线程并行 `build_single_file_kg` 为主；仅当 `use_hadoop=true` 且存在无本地 `pdf_text` 的文件时，才对这部分走 MapReduce（提取→清洗→分块），拉回后合并再构建。详见 `docs/OPTIMIZATION_SUGGESTIONS.md` 第六节。
- **MapReduce 管线**（供折中方案与大规模预处理使用）：
  - 文本提取（PDF → 文本）：`hadoop/mapreduce/pdf_extract/`
  - 文本清理：`hadoop/mapreduce/text_clean/mapper.py`
  - 文本分块：`hadoop/mapreduce/text_chunk/mapper.py`
- 本地或 Docker 下可通过 `docker-compose` 启动 Hadoop 集群（NameNode、DataNode、ResourceManager、NodeManager 等），笔记本可用但建议 8GB+ 内存；少量文件时 MapReduce 启动开销可能大于本地多线程，适合文件量较大时启用。

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

- **图检索**（`graph_retrieve`）：基于 Neo4j 的关系与实体查询
- **向量/文献检索**（`doc_search`）：基于 Chroma 嵌入与知识库文档
- **Hybrid RAG 混合检索**（`hybrid_retrieve`）：图 + Chroma 文档 + 关键词三路 RRF 融合
- **关键词检索**：备用方案（图检索无实体时由 `_keyword_search` 兜底）

上述能力封装为 Agent 可调用的工具，由 LLM 在推理中决定调用哪些、如何组合，而非固定流水线顺序。

### 3. Hybrid RAG（混合检索）详解

**Hybrid RAG** 将三路检索结果统一为 `HybridItem` 格式，经 RRF（Reciprocal Rank Fusion）融合后按 `content_key` 去重，输出排序后的综合结果。

| 检索源 | 说明 | 来源标识 |
|-------|------|----------|
| 图检索 | Neo4j 实体、邻居、路径 | `graph` |
| 文档检索 | Chroma 向量库（按 user_id 过滤） | `doc` |
| 关键词检索 | Neo4j CONTAINS 匹配 | `keyword` |

- **调用方式**：
  - **Agent 工具**：`hybrid_retrieve(query, top_k=10)`，Agent 在需要综合多源知识时自动调用
  - **RAG 管线**：`pipeline.answer(query, use_hybrid=True, user_id="xxx")`
  - **问答服务**：`run_query(question, use_hybrid=True, user_id="xxx")`
- **设计文档**：`docs/HYBRID_RAG_DESIGN.md`

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
- ✅ Agent 智能问答：兼容 RAG 检索与 LangGraph Agent，LLM 自主调用 RAG 工具（图检索、文献检索），支持多轮对话与流式输出
- ✅ RAG 作为工具：图检索、向量检索、**Hybrid RAG 混合检索**（图+Chroma+关键词 RRF 融合）封装为 Agent 工具，由 Agent 按需调用
- ✅ **多模态认知负荷评估**：行为埋点 + NASA-TLX主观问卷 + EEG生理信号预留接口，多模态加权融合量化认知负荷
- ✅ **NASA-TLX问卷评估**：简化版六维度评分（脑力/体力/时间需求、绩效、努力、挫败感），适老化设计
- ✅ **行为分析评分**：基于点击/回退/错误/耗时等行为特征的实时认知负荷评估
- ✅ **融合评估报告**：单次评估报告 + 趋势分析报告 + 周期汇总报告，多维度雷达图与个性化建议
- ✅ 分布式处理：基于 Hadoop 的分布式文本处理
- ✅ 异步任务管理：基于 Celery 的异步任务队列
- ✅ 多数据库支持：Neo4j + MySQL 数据持久化
- ✅ RESTful API：完整的 API 服务，与 Vue 前端联调（图谱、历史记录、知识库、认知负荷评估、模板下载等）
- ✅ 历史记录：统一存储与状态更新，支持分页与最多 1000 条，图谱构建/上传状态正确回显
- ✅ Docker 容器化：全系统容器化部署

### 2. 技术创新

- **Agent 架构**：LangGraph 编排 LLM 与 RAG 工具，替代固定 RAG 流水线，支持多轮与指代
- **Hybrid RAG 融合检索**：图 + Chroma 文档 + 关键词三路 RRF 融合，统一格式与去重；作为 Agent 工具由 LLM 决策调用与组合
- **多模态认知负荷评估**：行为分析 + NASA-TLX问卷 + EEG预留接口三模态融合，加权评分算法，支持雷达图可视化与个性化建议
- **适老化认知评估**：简化版NASA-TLX量表适老化改造，1-7分滑动评分，降低老年用户填写负担
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
- [ ] 增强 Agent 工具（更多检索源）
- [ ] 优化分布式处理性能，支持更大规模数据
- [x] **EEG硬件集成**：对接Muse S设备，实现EEG认知负荷评估（**已完成模拟器+硬件模式**）
- [ ] **眼动追踪集成**：预留眼动数据接口，支持多模态融合评估扩展
- [ ] **认知负荷实时预警**：基于融合评分的实时认知过载预警机制
- [ ] **个性化认知模型**：基于用户历史数据建立个性化认知负荷基线模型

## 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

- 项目维护者：[xiangyue247]
- 邮箱：[2303548451@qq.com]
- GitHub：前端：[https://github.com/xiangyun247/knowledge_graph_frontend]
          后端: [https://github.com/xiangyun247/knowledge_graph]

**项目状态**：活跃开发中  
**最后更新**：2026-03-31  
**版本**：v2.2.0（EEG Muse S硬件支持版）
