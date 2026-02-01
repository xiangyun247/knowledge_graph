# Docker 完善步骤 1：docker-compose 与 Dockerfile 一次构建通过

## 目标

- 检查并修正 `docker-compose.yml` 与 `docker/` 下各 Dockerfile，使**均可一次构建通过**。
- **统一**基础镜像版本与 Python 依赖（`requirements.txt`）。
- 确保 **backend 能连上** Neo4j、MySQL、Redis、Hadoop（配置与库名一致）。

---

## 1.1 当前文件与问题概览

| 文件 | 用途 | 发现的问题 |
|------|------|------------|
| `docker-compose.yml` | 编排所有服务 | MySQL 库名为 `knowledge_graph`，与 init 脚本创建的 `knowledge_graph_system` 不一致，导致 backend 连到空库。Celery 未依赖 MySQL 健康。 |
| `docker/Dockerfile.backend` | FastAPI 后端 | 使用 `requirements-minimal.txt`，缺少 Chroma/LangGraph 等，Agent 与知识库在容器内会缺依赖；且与「统一 requirements.txt」不一致。 |
| `docker/Dockerfile.celery` | Celery Worker | 已用 `requirements.txt`；需与 backend 一致，并增加对 MySQL 的依赖。 |
| `docker/Dockerfile.hadoop-python` | NameNode + Python | 基于 bde2020 镜像，Python 为系统自带的 3.5，仅装 pdfplumber，无 requirements.txt。 |
| `docker/Dockerfile.hadoop-datanode-python` | DataNode + Python | 同上。 |
| `docker/Dockerfile.hadoop-nodemanager-python` | NodeManager + Python | 自编译 Python 3.9，装 pdfplumber；与 namenode/datanode 的 Python 版本不一致，但不影响「一次构建通过」。 |

---

## 1.2 修改清单（按顺序执行）

### 步骤 A：统一 MySQL 库名（docker-compose）

- **原因**：`MYSQL/init_mysql.sql` 创建并使用的是数据库 `knowledge_graph_system`，表（如 `knowledge_graphs`、`history_records`）都在该库。`docker-compose.yml` 中 `MYSQL_DATABASE=knowledge_graph` 会使 backend/celery 连到库 `knowledge_graph`，该库在 init 后为空，导致接口无数据。
- **操作**：在 `docker-compose.yml` 中，将 **backend** 和 **celery-worker** 的 `MYSQL_DATABASE` 改为 `knowledge_graph_system`（与 init 脚本一致）。

### 步骤 B：Backend 使用统一 requirements.txt

- **原因**：当前 backend 使用 `requirements-minimal.txt`，缺少 chromadb、langgraph、langchain-*、numpy 等，容器内 Agent/知识库会报错；且与「统一使用 requirements.txt」不符。
- **操作**：在 `docker/Dockerfile.backend` 中，将 `COPY requirements-minimal.txt requirements.txt` 改为 `COPY requirements.txt .`，安装阶段使用 `pip install -r requirements.txt`。这样与 Celery 共用同一依赖文件，一次构建即可得到功能完整的后端。

### 步骤 C：Celery 依赖 MySQL 健康

- **原因**：Celery 任务可能访问 MySQL（如写历史、图谱状态），若 MySQL 未就绪即启动 worker，会连库失败。
- **操作**：在 `docker-compose.yml` 的 `celery-worker` 的 `depends_on` 中，增加对 `mysql` 的依赖，并使用 `condition: service_healthy`（与 backend 一致）。

### 步骤 D：统一基础镜像说明与 .dockerignore

- **原因**：文档与实现一致，避免后续维护混淆；.dockerignore 需确保 `requirements.txt` 不被排除。
- **操作**：在 `docker/README.md` 中将「Python 3.9-slim」改为「Python 3.10-slim」（与当前 Dockerfile 一致）。确认 `.dockerignore` 未排除 `requirements.txt`（当前已未排除，仅作核对）。

### 步骤 E：验证一次构建与连通性

- **构建**：在项目根目录执行  
  `docker-compose build --no-cache backend celery-worker hadoop-namenode hadoop-datanode hadoop-nodemanager`  
  确认无报错。
- **启动**：`docker-compose up -d`，等待各服务 healthy。
- **连通性**：对 backend 容器内执行健康检查或请求 `GET /docs`；检查 backend 日志中是否有 Neo4j/MySQL/Redis 连接成功或报错信息；Hadoop 通过 `HADOOP_NAMENODE` 环境变量由 backend 连接，确认无连接错误即可。

---

## 1.3 修改后的关键片段（供对照）

- **docker-compose.yml**  
  - backend / celery-worker 的 `MYSQL_DATABASE`：`knowledge_graph_system`  
  - celery-worker 的 `depends_on`：增加 `mysql: condition: service_healthy`

- **docker/Dockerfile.backend**  
  - `COPY requirements.txt .`  
  - `RUN pip install --no-cache-dir -r requirements.txt`

---

## 1.4 后续步骤（不在此次修改范围）

- Hadoop 三镜像的 Python 版本不完全统一（NameNode/DataNode 用系统 Python 3.5，NodeManager 用自编译 3.9），若需统一可放在「步骤 2」或后续优化。
- 环境变量与密钥抽离到 `.env`、编写 `DEPLOYMENT.md` 等，按 TODO_PHASES 的「二、Docker+上云」后续条目进行。
