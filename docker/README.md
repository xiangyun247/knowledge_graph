# Docker 配置文件说明

## 📁 文件结构

```
docker/
├── Dockerfile.backend              # 后端服务 Dockerfile
├── Dockerfile.celery               # Celery Worker Dockerfile
├── Dockerfile.frontend              # 前端构建参考（实际使用前端项目内 docker/Dockerfile）
├── Dockerfile.hadoop-python        # Hadoop NameNode（带 Python 支持）
├── Dockerfile.hadoop-datanode-python  # Hadoop DataNode（带 Python 支持）
├── nginx.conf                      # Nginx 配置参考（实际使用前端项目内 docker/nginx.conf）
└── .dockerignore                   # Docker 构建忽略文件
```

## 🐳 Dockerfile 说明

### Dockerfile.backend
- 用于构建 FastAPI 后端服务
- 基于 Python 3.10-slim
- 使用 `requirements.txt`，包含所有后端依赖（含 Agent、Chroma 等）
- 暴露端口 5001

### Dockerfile.celery
- 用于构建 Celery Worker
- 基于 Python 3.10-slim
- 使用 `requirements.txt`，与 backend 依赖一致；包含 Celery、Redis、MySQL 等
- 用于异步任务处理

### Dockerfile.hadoop-python
- 扩展 Hadoop NameNode 镜像
- 基于 `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8`
- 添加 Python 3.5.3 和 pip3
- 安装 pdfplumber 0.5.0（兼容 Python 3.5）
- 安装 ImageMagick（pdfplumber 依赖）
- 用于运行 MapReduce Python 脚本

### Dockerfile.hadoop-datanode-python
- 扩展 Hadoop DataNode 镜像
- 基于 `bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8`
- 添加 Python 3.5.3 和 pip3
- 安装 pdfplumber 0.5.0（兼容 Python 3.5）
- 安装 ImageMagick（pdfplumber 依赖）
- 用于运行 MapReduce Python 脚本

## 🚀 使用方法

### 构建镜像

```bash
# 构建后端镜像
docker build -f docker/Dockerfile.backend -t kg-backend .

# 构建 Celery 镜像
docker build -f docker/Dockerfile.celery -t kg-celery .

# 构建 Hadoop NameNode 镜像（带 Python 支持）
docker build -f docker/Dockerfile.hadoop-python -t hadoop-namenode-python .

# 构建 Hadoop DataNode 镜像（带 Python 支持）
docker build -f docker/Dockerfile.hadoop-datanode-python -t hadoop-datanode-python .
```

**注意：** 使用 `docker-compose up` 时会自动构建这些镜像。

### 前端服务

- 前端需单独仓库（如 `vue_test_style` 或 `knowledge_gragh_frontend`），且需包含 `docker/Dockerfile` 与 `docker/nginx.conf`
- 将前端项目放到与 `knowledge_gragh` 同级目录，或设置 `FRONTEND_CONTEXT` 指向前端路径
- 启动后访问 `http://localhost` 即可打开前端，`/api` 自动反代到 backend:5001

### 使用 Docker Compose（推荐）

```bash
# 启动所有服务（含 frontend，需先放置前端项目）
docker-compose up -d

# 仅启动后端与数据库（不含 frontend）
docker-compose up -d backend mysql neo4j redis

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f celery-worker

# 停止服务
docker-compose down
```

## 📝 注意事项

1. **环境变量**：确保 `.env` 文件配置正确
2. **数据持久化**：使用 Docker volumes 保存数据
3. **网络**：所有服务在 `kg-network` 网络中
4. **健康检查**：服务启动前会进行健康检查


