# Docker 配置文件说明

## 📁 文件结构

```
docker/
├── Dockerfile.backend              # 后端服务 Dockerfile
├── Dockerfile.celery               # Celery Worker Dockerfile
├── Dockerfile.hadoop-python        # Hadoop NameNode（带 Python 支持）
├── Dockerfile.hadoop-datanode-python  # Hadoop DataNode（带 Python 支持）
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

### 使用 Docker Compose（推荐）

```bash
# 启动所有服务
docker-compose up -d

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


