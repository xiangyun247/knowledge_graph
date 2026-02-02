# 部署说明

## 生产环境注意

- 部署前请将 `.env.example` 复制为 `.env` 并填写真实密码与 API Key。
- **务必修改** Neo4j、MySQL 的默认密码，不要使用示例中的占位或默认值。
- 不要将 `.env` 提交到代码仓库；`.env` 已加入 .gitignore。

---

## 一、端口一览

| 服务 | 宿主机端口 | 容器端口 | 说明 |
|------|------------|----------|------|
| **backend** | 5001 | 5001 | FastAPI API 与文档（/docs） |
| **Neo4j** | 7474 | 7474 | HTTP 控制台 |
| **Neo4j Bolt** | 7687 | 7687 | 驱动连接 |
| **MySQL** | 3307 | 3306 | 避免与本地 3306 冲突 |
| **Redis** | 6379 | 6379 | Celery Broker |
| **Hadoop NameNode Web** | 9870 | 9870 | HDFS 管理界面 |
| **HDFS** | 9000 | 8020 | HDFS 客户端（容器内 8020） |
| **Hadoop DataNode** | 9864 | 9864 | DataNode Web |
| **YARN ResourceManager** | 8088 | 8088 | YARN 管理界面 |
| **NodeManager** | 8042 | 8042 | 节点状态 |
| **HistoryServer** | 8188 | 8188 | MR 任务历史（可选） |

---

## 二、健康检查

以下服务配置了 healthcheck，**backend** 会等它们全部 healthy 后再启动：

| 服务 | 检查方式 | 间隔 | 超时 | 启动宽限 |
|------|----------|------|------|----------|
| **redis** | `redis-cli ping` | 10s | 5s | - |
| **mysql** | `mysqladmin ping -h localhost -u root -p...` | 10s | 5s | 30s |
| **neo4j** | `cypher-shell -u neo4j -p ... RETURN 1` | 30s | 10s | 60s |
| **hadoop-namenode** | `curl -f http://localhost:9870` | 30s | 10s | 60s |

- **hadoop-datanode** 无 healthcheck，依赖 `depends_on: hadoop-namenode (healthy)`。
- **hadoop-historyserver** 可能显示 `unhealthy`，属常见情况，不影响后端与 MR 任务；仅影响 8188 任务历史页。

---

## 三、首次初始化

### 1. MySQL

- **时机**：MySQL 容器**首次**启动且数据卷为空时，会自动执行 `MYSQL/init_mysql.sql`。
- **内容**：创建数据库 `knowledge_graph_system`，建表 `knowledge_graphs`、`history_records`、`users` 及索引，并插入示例图谱与历史记录。
- **注意**：若数据卷已存在（例如之前跑过），不会再次执行 init；要「重新初始化」需删卷后重启（见下方故障排查）。

### 2. Neo4j

- **时机**：首次启动时设置 `.env` 中的 `NEO4J_PASSWORD`（或 compose 默认值），并加载 apoc 插件。
- **注意**：若曾跑过且卷里有旧数据，再次启动可能报「Neo4j is already running」并 exit(1)，需删 Neo4j 数据卷后重新启动（见下方故障排查）。

### 3. Backend / Celery

- 无单独初始化步骤；启动后依赖 MySQL、Neo4j、Redis、Hadoop 均 healthy，再对外提供服务。
- DeepSeek API Key 在 `.env` 中配置；未配置时 Agent/问答相关功能不可用，其余接口可正常使用。

---

## 四、Docker Compose 启动（推荐）

### 1. 环境准备

```bash
# 复制环境变量（Windows PowerShell）
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

编辑 `.env`，将 `your-neo4j-password-here`、`your-mysql-root-password-here`、`your-mysql-kg-password-here`、`your-deepseek-api-key-here` 改为真实值。

### 2. 构建与启动

```bash
# 在项目根目录执行
docker-compose up -d

# 若需重新构建镜像（例如改过 Dockerfile 或 requirements.txt）
docker-compose up -d --build
```

### 3. 查看状态

```bash
docker-compose ps
```

期望：backend、neo4j、mysql、redis、celery-worker、hadoop-namenode 等为 **Up** 或 **(healthy)**；hadoop-historyserver 为 **(unhealthy)** 可忽略。

### 4. 验证

- API 文档：<http://localhost:5001/docs>
- Neo4j 控制台：<http://localhost:7474>
- YARN：<http://localhost:8088>
- HDFS：<http://localhost:9870>

---

## 五、常用命令

| 命令 | 说明 |
|------|------|
| `docker-compose up -d` | 后台启动所有服务 |
| `docker-compose ps` | 查看容器状态 |
| `docker-compose logs -f backend` | 查看 backend 日志（Ctrl+C 退出） |
| `docker-compose logs --tail=50 neo4j` | 查看 Neo4j 最近 50 行日志 |
| `docker-compose restart backend` | 仅重启 backend |
| `docker-compose down` | 停止并删除容器（不删数据卷） |
| `docker-compose down -v` | 停止并删除容器及**所有**数据卷（慎用） |

---

## 六、故障排查

### Neo4j 启动失败（exit 1）

- **现象**：`kg-neo4j` 状态为 Exited (1)，日志中有「Neo4j is already running」。
- **原因**：旧数据卷导致入口脚本在「二次初始化」时失败。
- **处理**：删 Neo4j 数据卷后重新启动（会清空图数据）：
  ```bash
  docker-compose down
  docker volume rm knowledge_gragh_neo4j_data
  docker-compose up -d
  ```

### MySQL 需重新初始化

- 若希望重新执行 `init_mysql.sql`（清空并重建库表），需删 MySQL 数据卷：
  ```bash
  docker-compose down
  docker volume rm knowledge_gragh_mysql_data
  docker-compose up -d
  ```

### hadoop-historyserver 显示 unhealthy

- 不影响后端与 Hadoop 任务执行，可忽略；仅 8188 任务历史页可能无法访问或加载慢。

### Backend 无法连 Neo4j/MySQL

- 确认 `.env` 中 `NEO4J_PASSWORD`、`MYSQL_PASSWORD` 与 compose 中 neo4j、mysql 的配置一致（若未改 .env，则使用 compose 内默认值）。
- 确认 `docker-compose ps` 中 neo4j、mysql 为 **(healthy)** 后再看 backend 日志。

---

## 七、持久化与备份

### 1. 数据卷（持久化）

以下服务使用 **named volume**，数据在 `docker compose down` 后仍保留；仅在使用 `docker compose down -v` 或 `docker volume rm` 时才会删除。

| 服务 | 卷名（前缀为项目目录名，如 `knowledge_graph_`） | 说明 |
|------|-----------------------------------------------|------|
| **MySQL** | `mysql_data` | 映射到容器内 `/var/lib/mysql`，库表与用户数据均在此。 |
| **Neo4j** | `neo4j_data`、`neo4j_logs` | 图数据与日志。 |
| **Redis** | `redis_data` | 映射到容器内 `/data`，已开启 `appendonly yes`，重启不丢。 |
| **HDFS**（仅全栈） | `namenode_data`、`datanode_data` | 全栈 `docker-compose.yml` 中 HDFS 元数据与块数据。 |

- **精简版**（`docker-compose.cloud-minimal.yml`）仅使用：`redis_data`、`neo4j_data`、`neo4j_logs`、`mysql_data`。
- 查看卷：`docker volume ls`（名称格式为 `项目名_卷名`，如 `knowledge_graph_mysql_data`）。
- 云主机上若需长期保留数据，避免对上述卷执行 `down -v`；如需迁移，可备份卷或使用云盘挂载到宿主机目录再在 compose 中改为 bind mount。

### 2. 备份策略建议

| 组件 | 方式 | 示例命令 / 说明 |
|------|------|-----------------|
| **MySQL** | mysqldump | `docker exec kg-mysql mysqldump -u root -p<MYSQL_ROOT_PASSWORD> --single-transaction --databases knowledge_graph_system > backup_mysql_$(date +%Y%m%d).sql` |
| **Neo4j** | 卷备份或 Cypher 导出 | 社区版可定期备份 `neo4j_data` 卷（如 `docker run --rm -v knowledge_graph_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j_data_$(date +%Y%m%d).tar.gz -C /data .`）；或按业务用 Cypher 导出关键子图。 |
| **Redis** | RDB 文件 | 已开启 AOF，数据在 `redis_data` 卷中；需冷备份时可 `docker cp kg-redis:/data ./redis_backup` 或定期 `redis-cli BGSAVE` 后拷贝 RDB。 |

- 建议将备份文件存到对象存储或另一台机器，并按周期（如每日/每周）执行。
- 恢复：MySQL 用 `mysql ... < backup_xxx.sql`；Neo4j 用 `neo4j-admin load`；Redis 用替换 RDB 后重启。

---

## 八、相关文档

- **Docker 步骤 1**：`docs/DOCKER_STEP1.md`（compose 与 Dockerfile、MySQL 库名、依赖）
- **Docker 步骤 2**：`docs/DOCKER_STEP2.md`（环境变量与密钥管理）
- **云主机与后端上云**：`docs/DEPLOYMENT_CLOUD_STEP4.md`（学生向简明步骤）
- **前端上云（步骤 8）**：`docs/DEPLOYMENT_FRONTEND_STEP8.md`（Nginx 托管 Vue 静态站 + /api 反向代理）
- **API 接口**：`docs/API.md`；启动后也可查看 <http://localhost:5001/docs> 。
