# 系统架构说明

本文档描述「胰明」知识图谱生成与智能问答系统的架构、数据流与技术栈。

---

## 一、整体架构

```mermaid
flowchart TB
    subgraph 用户层
        A1[API 调用]
        A2[Web 界面]
        A3[测试脚本]
    end

    subgraph API 层
        B[FastAPI 服务]
        B1[健康检查]
        B2[统计查询]
        B3[实体搜索]
        B4[Agent 问答]
        B5[数据导入]
    end

    subgraph 业务逻辑层
        C1[知识图谱生成]
        C2[Agent LangGraph]
        C3[RAG 工具]
        C4[任务管理]
        C5[实体提取器]
        C6[LLM + bind_tools]
        C7[图检索/向量检索]
        C8[会话记忆]
    end

    subgraph 数据处理层
        D1[Hadoop 分布式处理]
        D2[Celery 异步任务]
        D3[PDF 提取]
        D4[文本处理]
        D5[文本清理]
        D6[文本分块]
        D7[实体关系提取]
    end

    subgraph 数据存储层
        E1[(Neo4j 图数据库)]
        E2[(MySQL 关系数据库)]
        E3[(Chroma 向量库)]
        E4[本地存储]
    end

    A1 & A2 & A3 --> B
    B --> B1 & B2 & B3 & B4 & B5
    B --> C1 & C2 & C3 & C4
    C2 --> C5 & C6 & C7 & C8
    C1 & C2 & C3 --> D1 & D2 & D3 & D4
    D1 & D2 --> D5 & D6 & D7
    D1 & D2 & D3 & D4 --> E1 & E2 & E3 & E4
```

---

## 二、数据流

### 1. 知识图谱构建流程

```mermaid
flowchart LR
    A[PDF/文本] --> B[正文提取]
    B --> C[文本分块]
    C --> D[LLM 实体关系提取]
    D --> E[Neo4j 写入]
    E --> F[MySQL graph_data]
```

### 2. Agent 智能问答流程

```mermaid
flowchart TB
    A[用户问题] --> B[Agent 节点]
    B --> C{LLM 决策}
    C -->|调用工具| D[Tools 节点]
    D --> E[图检索]
    D --> F[文献检索]
    E & F --> G[结果合并]
    G --> B
    C -->|直接回答| H[输出 answer + sources]
```

### 3. 部署拓扑（Docker Compose）

```mermaid
flowchart TB
    subgraph 宿主机
        F[Frontend :80]
        B[Backend :5001]
        C[Celery Worker]
        N[(Neo4j)]
        M[(MySQL)]
        R[(Redis)]
        H[Hadoop]
    end

    U[用户] --> F
    F -->|/api 反代| B
    B --> N & M & R & H
    C --> N & M & R
```

---

## 三、技术栈

| 层级     | 技术           | 说明                    |
|----------|----------------|-------------------------|
| 前端     | Vue 2 + Element UI | Web 界面、图谱可视化 |
| API      | FastAPI        | RESTful 接口、OpenAPI   |
| 业务     | LangGraph Agent | 智能问答编排            |
| RAG      | 图检索 + Chroma | 图谱与文献检索          |
| 任务     | Celery + Redis | 异步任务队列            |
| 分布式   | Hadoop         | 大规模文本处理          |
| 图数据库 | Neo4j          | 知识图谱存储            |
| 关系库   | MySQL          | 元数据、历史、用户      |
| 向量库   | Chroma         | 文档嵌入与检索          |
| LLM      | DeepSeek 等    | 多模型支持              |

---

## 四、相关文档

- **API 接口**：`docs/API.md`，或启动后访问 `/docs`
- **部署说明**：`docs/DEPLOYMENT.md`
- **演示脚本**：`docs/DEMO_SCRIPT.md`
