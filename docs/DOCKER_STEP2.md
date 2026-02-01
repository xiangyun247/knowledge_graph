# Docker 步骤 2：环境变量与密钥管理 — 具体修改清单

## 目标

- 将敏感信息（Neo4j 密码、MySQL 密码、DeepSeek API Key）从 docker-compose 抽离到 `.env`。
- 完善 `.env.example`，列出所有占位与说明，便于他人/上云时复制为 `.env` 并填写。
- 确保 `.env` 已被 git 忽略；生产环境务必修改默认密码。

---

## 文件清单（要改/要新建）

| 序号 | 文件 | 操作 | 说明 |
|------|------|------|------|
| 1 | `.env.example` | **修改** | 补全 Docker 用变量、占位说明；修正编码为 UTF-8；增加「Docker Compose 用」小节。 |
| 2 | `docker-compose.yml` | **修改** | Neo4j、MySQL、backend、celery-worker 的密码/密钥改为 `${VAR:-默认值}`，从 .env 读取。 |
| 3 | `.gitignore` | **核对** | 确认已有 `.env`，无需修改。 |
| 4 | `docs/DEPLOYMENT.md` 或 README | **补充** | 增加一句：生产环境务必修改默认密码、勿提交 `.env`。 |

---

## 1. `.env.example` — 每处写什么

**路径**：项目根目录 `.env.example`  

**要求**：UTF-8 编码；包含「本地/开发」与「Docker Compose 用」两类说明。

**建议内容**（可直接替换原文件）：

```ini
# ==================== Docker Compose 用（复制为 .env，docker-compose 会读取） ====================
# 生产环境务必修改以下密码，且不要将 .env 提交到仓库。

# Neo4j（容器内与 backend/celery 连接用）
NEO4J_PASSWORD=your-neo4j-password-here

# MySQL root 与业务账号
MYSQL_ROOT_PASSWORD=your-mysql-root-password-here
MYSQL_USER=kg_user
MYSQL_PASSWORD=your-mysql-kg-password-here

# DeepSeek API（Agent/问答用，可为空则相关功能不可用）
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 应用运行环境（可选）
DEBUG=False
ENVIRONMENT=production
LOG_LEVEL=INFO

# ==================== 本地开发用（非 Docker 时 run.py 等会读取） ====================
# HOST=0.0.0.0
# PORT=5001
# NEO4J_URI=bolt://localhost:7687
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_DATABASE=knowledge_graph_system
# REDIS_HOST=localhost
# REDIS_PORT=6379
```

说明：Docker 下 backend/celery 的 `NEO4J_URI`、`MYSQL_HOST` 等由 compose 写死为服务名，无需在 .env 重复；本地开发可取消注释上面「本地开发用」并改 host/port。

---

## 2. `docker-compose.yml` — 每处改什么

**原则**：敏感项用 `${VAR:-默认值}`，未设 .env 时用默认值保证能起；生产环境在 .env 中覆盖。

| 服务 | 原写法 | 改为 |
|------|--------|------|
| **neo4j** | `NEO4J_AUTH=neo4j/a2303548451` | `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-a2303548451}` |
| **neo4j** healthcheck | `-p", "a2303548451"` | `-p", "${NEO4J_PASSWORD:-a2303548451}"`（注意 YAML 中需用引号） |
| **mysql** | `MYSQL_ROOT_PASSWORD=root123` | `MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-root123}` |
| **mysql** | `MYSQL_USER=kg_user` | `MYSQL_USER=${MYSQL_USER:-kg_user}` |
| **mysql** | `MYSQL_PASSWORD=kg_password` | `MYSQL_PASSWORD=${MYSQL_PASSWORD:-kg_password}` |
| **mysql** healthcheck | `-proot123` | `-p${MYSQL_ROOT_PASSWORD:-root123}` |
| **backend** | `NEO4J_PASSWORD=a2303548451` | `NEO4J_PASSWORD=${NEO4J_PASSWORD:-a2303548451}` |
| **backend** | `MYSQL_USER=kg_user`、`MYSQL_PASSWORD=kg_password` | `MYSQL_USER=${MYSQL_USER:-kg_user}`、`MYSQL_PASSWORD=${MYSQL_PASSWORD:-kg_password}` |
| **celery-worker** | `NEO4J_PASSWORD=a2303548451`、`MYSQL_USER`/`MYSQL_PASSWORD` | 同 backend，改为 `${...}` |

说明：DeepSeek 相关已在 compose 中用 `${DEEPSEEK_API_KEY:-}` 等，无需再改。

---

## 3. `.gitignore` — 核对

**路径**：项目根目录 `.gitignore`  

**核对**：存在一行 `.env`（且未用 `!.env.example` 排除示例文件）。当前已有，无需修改。

---

## 4. 生产环境说明 — 写在哪、写什么

**建议**：在 `docs/DEPLOYMENT.md` 开头或 README 的「部署」小节增加一段：

```markdown
## 生产环境注意

- 部署前请将 `.env.example` 复制为 `.env` 并填写真实密码与 API Key。
- **务必修改** Neo4j、MySQL 的默认密码，不要使用示例中的占位或默认值。
- 不要将 `.env` 提交到代码仓库；`.env` 已加入 .gitignore。
```

若 `DEPLOYMENT.md` 为空或不存在，可只写上述一段；若 README 已有部署说明，在该节下追加上述三条即可。

---

## 5. 使用方式（给他人/上云）

1. 复制示例：`cp .env.example .env`（Windows：`copy .env.example .env`）。
2. 编辑 `.env`，将 `your-*-password-here`、`your-deepseek-api-key-here` 改为真实值。
3. 启动：`docker-compose up -d`；compose 会自动读取项目根目录下的 `.env`。

---

## 6. 校验

- 未创建 `.env` 时：`docker-compose config` 应能解析，且使用的为 compose 内默认值。
- 创建 `.env` 并填写 `NEO4J_PASSWORD=test123` 后：`docker-compose config` 中对应服务环境里应出现 `test123`（或 `neo4j/test123`）。
