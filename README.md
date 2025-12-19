# 胰腺炎知识图谱 RAG 系统（Pancreatitis-KG-RAG）

> 基于 **Neo4j 图数据库 + 检索增强生成（RAG）+ FastAPI** 的医疗知识图谱问答系统。  
> 当前以胰腺炎相关疾病为核心，支持：疾病—症状—治疗—科室—并发症等医学知识的结构化存储与问答。

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

本项目的目标是构建一个 **胰腺炎相关的医疗知识图谱 + 智能问答系统**，主要擅长处理：

- “某疾病有哪些典型症状？”
- “某疾病应该看什么科？”
- “某药物主要用于治疗哪些疾病？”
- “出现某个症状，可能与哪些疾病相关？”

核心设计思路：

1. 用 **Neo4j** 存储疾病、症状、治疗、药物、科室、并发症等实体与关系。  
2. 用 **LLM（DeepSeek）** 对医学文本（论文/指南/说明）进行实体关系抽取，自动构建知识图谱。  
3. 用 **图检索 + 规则意图识别** 处理结构化问题（例如“什么症状、怎么治疗、看什么科”等）。  
4. 在图谱答案不足时，**可选** 调用 RAG 流水线综合图谱与文本信息生成回答。  

---

## 🧩 系统架构

```text
           ┌──────────────────────────┐
           │        FastAPI API       │
           │   /query /search /stats  │
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
               ┌────────┴────────┐
               │   Neo4j 图数据库 │
               └──────────────────┘
 ```
⭐ 核心功能
1. 医疗知识图谱（Neo4j）

实体类型包括：Disease、Symptom、Treatment、Medicine、Examination、Department、Complication、RiskFactor 等。

关系类型包括：HAS_SYMPTOM、TREATED_BY、USES_MEDICINE、REQUIRES_EXAM、BELONGS_TO、CAUSES、LEADS_TO、ASSOCIATED_WITH、INCREASES_RISK 等。

scripts/init_database.py 会为每个实体类型创建唯一约束，并构建全文索引。

2. 图检索（GraphRetriever）

基于疾病/症状等实体，从 Neo4j 中进行多跳检索。

用于支持：

疾病 → 症状列表

疾病 → 用药 / 治疗措施

疾病 → 就诊科室

症状 → 可能疾病

药物 → 针对疾病

3. 意图识别 + 实体抽取

由 EntityExtractor 实现：

启动时从 Neo4j 加载所有 Disease / Symptom / Drug 名称到内存。

在用户问题中用“最长匹配”方式抽取疾病/症状/药物实体。

用正则模式识别意图：

“什么症状 / 有哪些症状 / 临床表现” → 症状查询

“怎么治疗 / 用什么药” → 治疗查询

“看什么科 / 挂哪个科” → 科室查询

“某症状可能是什么病” → 病因查询

“某药有什么作用 / 治疗什么病” → 药物查询

4. RAG（Retrieval-Augmented Generation，可选）

在规则 & 图查询无法找到合适答案时，降级调用 RAGPipeline：

默认策略：图检索为主（use_graph=True），向量检索可关闭或作为补充。

使用 DeepSeek Chat 作为生成模型。

当前推荐：系统主打“图谱 + 规则问答”，RAG 作为补充能力；Embedding 部分可根据实际需要逐步增强。

🖥️ 运行环境
组件	要求 / 说明
Python	≥ 3.9
Neo4j	4.x / 5.x（本地或 Aura 均可）
FastAPI	最新版
Uvicorn	最新版
DeepSeek	需要可用的 API Key
Embedding	可用本地模型（例如 bge-large-zh）
系统平台	Windows / Linux / macOS 均可
📁 项目结构

（略去无关文件，仅列核心）

project_root/
│  api_server.py               # FastAPI 主服务
│  config.py                   # 全局配置（Neo4j / LLM / RAG / 日志等）
│  .env                        # 环境变量配置
│  README.md                   # 本文档
│
├─scripts/                     # 工具脚本集合
│    init_database.py          # 创建索引 + 约束 + 导入初始胰腺炎知识
│    import_data.py            # 文本/JSON/目录导入（通用版本）
│    import_disease_data.py    # 医疗 JSON 数据导入（MedicalDataImporter）
│    import_pdf.py             # PDF 医学文献导入（带清洗）
│    test_system.py            # 系统级测试（7 项）
│    diagnose_search.py        # 搜索问题诊断脚本
│
├─db/
│    neo4j_client.py           # Neo4j 客户端封装（连接 / 读写 / 统计）
│
├─llm/
│    client.py                 # DeepSeek LLM 客户端封装（健康检查 / 调用）
│
├─rag/
│    rag_pipeline.py           # 检索增强生成管线
│    query_parser.py           # 查询解析器（意图/实体/关键词）
│    graph_retriever.py        # 图检索器（GraphRetriever）
│
├─backend/
│    app.py                    # 服务启动入口
├─kg/
│    builder.py                # KnowledgeGraphBuilder（从文本构建图谱）
│
└─data/
     raw/                      # 原始数据（txt / pdf / json 等）
     processed/                # 处理后数据
     examples/                 # 示例数据

⚙️ 配置说明

所有配置由 config.py 统一管理，并从 .env 读取：

示例 .env（请按实际环境调整）：

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

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TEMPERATURE=0.7

# Embedding（可选，当前不强依赖）
USE_LOCAL_EMBEDDING=True
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIM=1024

# RAG 配置
VECTOR_TOP_K=5
MAX_GRAPH_DEPTH=3
# 推荐在仅使用图检索时：
# VECTOR_WEIGHT=0.0
# GRAPH_WEIGHT=1.0


⚠ 若 NEO4J_PASSWORD 或 DEEPSEEK_API_KEY 未配置，config.py 会给出明确错误/警告。

🚀 快速启动
1️⃣ 安装依赖
pip install -r requirements.txt
# 如果要使用 PDF 导入：
pip install pdfplumber

2️⃣ 配置 .env

将上述示例 .env 放到项目根目录，并填入你自己的 Neo4j 密码与 DeepSeek Key。

3️⃣ 初始化数据库
python scripts/init_database.py


它会自动：

检查并显示当前配置摘要；

创建实体唯一约束与全文索引；

使用 KnowledgeGraphBuilder 导入一段胰腺炎相关基础知识文本；

在日志中输出 Neo4j 节点数、关系数、标签数、关系类型数。

4️⃣ 启动 API 服务
python api_server.py


默认访问地址：

根路径：http://localhost:5001/

文档（Swagger UI）：http://localhost:5001/docs

启动时会：

连接 Neo4j；

通过 EntityExtractor 从数据库加载所有疾病/症状/药物实体；

初始化 RAGPipeline（如果配置允许）；

🔌 API 说明
GET /

返回服务状态、版本等基本信息。

GET /health

用于健康检查，验证 Neo4j 连接及组件状态。

GET /stats

返回知识图谱统计信息，包括实体类型计数和关系类型计数。

GET /search

查询参数：

entity_type: Disease / Symptom / Drug / Department

keyword: 模糊匹配关键字

limit: 返回数量上限

内部逻辑使用正则进行模糊匹配：

GET /search?entity_type=Disease&keyword=胰腺炎&limit=10

POST /query

智能问答入口。请求体示例：

{
  "question": "急性胰腺炎有什么典型症状？",
  "max_results": 5
}


内部处理顺序：

实体提取 + 意图识别（EntityExtractor）；

若识别为：

症状查询 → 调 query_disease_symptoms；

治疗查询 → 调 query_disease_treatment；

科室查询 → 调 query_disease_department；

病因查询（由症状出发） → 调 query_symptom_diseases；

药物查询 → 调 query_drug_info。

若以上规则不能处理，并且 RAGPipeline 可用：

调用 RAGPipeline.answer(...)，返回自然语言回答；

若 RAG 也不可用 / 失败，则返回一个提示用户如何提问的 fallback。

📥 数据导入方式
1. 纯文本 / 目录导入

使用 scripts/import_data.py 中的 DataImporter：

支持功能：

从单个 .txt 文件导入：

按固定长度切分为多个片段；

每段调用 KnowledgeGraphBuilder.process_text 构建图谱；

从目录批量导入：扫描 *.txt 和 *.json 文件逐个导入。

2. JSON 医疗数据导入

使用 scripts/import_disease_data.py 中的 MedicalDataImporter：

JSON 格式示例：

{
  "diseases": [
    {"name": "急性胰腺炎", "category": "消化系统", "description": "...", "department": "消化内科"}
  ],
  "symptoms": [
    {"name": "上腹部疼痛", "severity": "重", "description": "..."}
  ],
  "drugs": [
    {"name": "某抗生素", "type": "抗菌药", "usage": "...", "dosage": "...", "treats": ["急性胰腺炎"]}
  ],
  "departments": [
    {"name": "消化内科", "description": "..."}
  ]
}


导入逻辑包括：

导入疾病、症状、药物、科室节点；

创建：

疾病-症状：(Disease)-[:HAS_SYMPTOM]->(Symptom)；

药物-疾病：(Drug)-[:TREATS]->(Disease)；

疾病-科室：(Disease)-[:BELONGS_TO]->(Department)。

⚠ 注意：import_from_json(..., clear_existing=True) 会清空现有数据库，请谨慎使用。

3. PDF 医学文献导入（带清洗）

使用我们扩展的 scripts/import_pdf.py：

python scripts/import_pdf.py "data/raw/某篇医学论文.pdf"


流程：

用 pdfplumber 逐页提取文本；

对文本做医学场景清洗（仅保留与疾病/症状/治疗等相关的正文）：

截断 “参考文献 / References / 致谢” 之后的所有内容；

去掉图表标题、页眉页脚、页码、纯数字/公式行；

去掉 [1] / [2-5] 这类文献标号；

去掉 (Smith 2020) 等作者-年份引用；

去掉 URL / 邮箱。

将清洗后的文本按 chunk（默认约 1000 字）分段；

使用 KnowledgeGraphBuilder.process_text 逐段构建知识图谱；

在终端输出：

分段总数、成功处理段数；

新增实体数、新增关系数；

出错段数。

典型导入规模示例（真实案例）：## 📚 示例：从一篇 PDF 到可查询知识图谱

下面用一个真实的场景，走一遍完整流程：  
**从一篇“急性胰腺炎相关医学论文 / 指南 PDF” → 导入 Neo4j → 用 API 进行问答。**

### 1️⃣ 准备 PDF 文件

1. 找一篇与你关注领域相关的医学 PDF，比如：  
   - 急性胰腺炎的急诊救治新进展  
   - 某疾病的诊治指南  
   - 某疾病的健康科普手册  

2. 将文件放到项目的 `data/raw/` 目录下，例如：

```text
data/
  raw/
    急性胰腺炎的急诊救治新进展.pdf
路径和文件名可以自定义，只要记得在命令里写对。
```
2️⃣ 使用 import_pdf.py 导入 PDF
在项目根目录执行：

bash
复制代码
# Windows 示例（注意路径用双引号包起来）
python scripts/import_pdf.py "data/raw/急性胰腺炎的急诊救治新进展(1).pdf"
导入流程包括：

使用 pdfplumber 逐页提取 PDF 文本。

对文本进行医学场景清洗：

切掉“参考文献 / References / 致谢”等之后的所有内容；

去掉图表标题（图1 / Figure 1 / 表1 / Table 1 等）；

去掉页眉页脚、页码、纯数字/公式行；

去掉 [1]、[2-5] 等文献标记；

去掉 (Smith 2020)、(Wang et al., 2019) 等作者-年份引用；

去掉 URL / 邮箱等与医学知识无关的噪音。

将清洗后的正文按 chunk（默认约 1000 字）分段。

对每个 chunk 调用 KnowledgeGraphBuilder.process_text，写入 Neo4j。

终端上你会看到类似输出：

text
复制代码
📄 PDF 医学文献导入工具（带清洗）
...
清洗文本分为 13 段（chunk_size=1000）
...
✅ 第 1 段处理完成: 新增实体=15, 新增关系=13
✅ 第 2 段处理完成: 新增实体=12, 新增关系=11
...
PDF 导入完成!
   文本分段: 13/13
   新增实体: 170
   新增关系: 161
   出错段数: 0
一个大约 12000 字 的医学 PDF，导出 百级的实体和关系 是非常正常的量级。

3️⃣ 在 Neo4j 中验证导入结果
打开 Neo4j Browser，执行下面几条查询：

查看整体规模变化：

cypher
复制代码
MATCH (n) RETURN count(n) AS node_count;
MATCH ()-[r]->() RETURN count(r) AS relationship_count;
如果和导入前相比，节点数、关系数有所增加，说明新图谱知识已经写入。

按疾病名称检查节点：

假设你的 PDF 和“急性胰腺炎”相关，可以这样查：

cypher
复制代码
MATCH (d:Disease)
WHERE d.name CONTAINS "胰腺炎"
RETURN d
LIMIT 10;
查看疾病相关的关系：

cypher
复制代码
MATCH (d:Disease)-[r]->(x)
WHERE d.name CONTAINS "胰腺炎"
RETURN d, type(r) AS rel_type, x
LIMIT 20;
你应该能看到和 PDF 内容对应的：

疾病 → 症状（HAS_SYMPTOM）

疾病 → 治疗方式 / 药物（TREATED_BY / USES_MEDICINE）

疾病 → 科室（BELONGS_TO）

疾病 → 并发症 / 风险因素 等

4️⃣ 使用 API /query 进行问答
确保 api_server.py 已经启动：

bash
复制代码
python api_server.py
# 默认监听 http://localhost:5001
然后通过 Swagger UI 或其他工具（Postman / curl）调用 /query 接口：

示例问题 1：疾病症状

json
复制代码
POST http://localhost:5001/query
Content-Type: application/json

{
  "question": "急性胰腺炎有哪些典型症状？",
  "max_results": 5
}
预期行为：

EntityExtractor 从问题中识别出 “急性胰腺炎” 这个疾病实体；

意图识别为 “症状查询”；

调用图查询函数，返回该疾病在图谱中挂载的所有症状节点；

生成类似这样的回答（示意）：

text
复制代码
急性胰腺炎的主要症状包括：

• 上腹部疼痛
• 恶心、呕吐
• 发热
• 腹胀
...

（具体内容取决于你导入的数据）
示例问题 2：治疗方式

json
复制代码
{
  "question": "急性胰腺炎一般如何治疗？",
  "max_results": 5
}
预期行为：

意图识别为 “治疗查询”；

调用图查询获取所有与该疾病相关的治疗措施 / 药物；

返回一个包含治疗列表 + 注意事项提示的回答。

通过以上步骤，你就完成了一个完整链路：

一篇医学 PDF → 清洗抽取 → 写入知识图谱 → 通过 API 进行结构化医学问答。

你可以重复这个流程，不断导入新的论文/指南，让图谱和问答能力持续“长胖”。

原始文本长度约 12000 字

切分为 13 个 chunk

新增实体约 170 个

新增关系约 160 条

出错段数为 0 —— 属于非常正常、健康的导入结果（图谱既不稀疏也不过度膨胀）。

🧠 RAG 工作机制

本项目以 “图谱优先” 为核心设计，RAG 作为可选增强能力。

RAGPipeline 的典型调用方式（参考 test_system.py）：

解析查询：

使用 QueryParser 从自然语言问题中抽取意图、实体、关键词等。

图检索（GraphRetriever）：

从 Neo4j 中检索与关键实体相关的节点和关系。

（可选）向量检索：

使用 Embedding 对文本片段进行编码，基于相似度检索。

当前项目中，Embedding 部分默认可关闭（或使用占位向量），建议图检索优先。

LLM 生成回答：

将检索到的结构化信息和文本作为上下文，调用 DeepSeek Chat 生成最终回答。

返回 answer + sources + confidence 信息。

🧪 测试与诊断
1. 系统级测试：scripts/test_system.py

依次测试七个部分：

Neo4j 连接与统计信息

LLM 连接健康

Embedding 客户端

查询解析器（QueryParser）

图检索器（GraphRetriever）

RAG 流水线

端到端问答（多条胰腺炎相关问题）

运行：

python scripts/test_system.py

2. 搜索诊断：scripts/diagnose_search.py

专门用于诊断 Neo4j 中疾病搜索行为：

查看前若干疾病/症状节点；

测试 CONTAINS 模糊匹配；

测试正则匹配；

测试精确匹配。

可在你导入新数据后，用它来确认搜索逻辑是否符合预期。

⚠ 注意事项 & 已知限制

Embedding 目前为可选 / 占位状态

如果未配置真实 Embedding 模型，系统会使用占位向量并在日志中提示；

推荐在此阶段主要依赖 图检索 + 规则问答，RAG 作为补充，不要过度依赖语义向量排序。

FastAPI 的 on_event 已经有弃用警告

日志中会看到关于 @app.on_event("startup") / "shutdown" 的 DeprecationWarning；

这不影响当前使用，未来可以迁移到新的 lifespan API。

医学语义的正确性

图谱关系的正确性取决于 LLM 的抽取质量和原始文献的可靠性；

对于关键医疗结论，仍建议由专业医生审核，不应直接用于临床决策。

PDF 文本质量依赖文档本身格式

扫描版、双栏排版、复杂表格会影响 PDF 文本解析质量；

清洗规则尽量通用，但在少数文献上可能需要进一步微调。

📝 TODO / 未来扩展

 将 FastAPI 生命周期迁移到 lifespan 风格，消除弃用警告。

 接入真实的 Embedding 模型，并设计混合检索策略（Graph + Vector）。

 为 PDF 导入增加更智能的章节识别（如只抽取 “诊断 / 治疗 / 预后 / 推荐”等部分）。

 提供前端 Demo（如简单的 Web 聊天界面 / 医学知识查询面板）。

 更丰富的医学领域扩展：从胰腺炎扩展到消化系统、重症医学等。

🙌 致谢

本项目最初以 胰腺炎知识图谱 为实验场景，逐步演化为一个可扩展的医疗知识图谱 RAG 框架。
欢迎在此基础上扩展更多疾病、添加更多数据源、接入更强大的模型与检索方式。

如需二次开发或部署到生产环境，请根据自身需求完善安全审查和医学内容审核流程