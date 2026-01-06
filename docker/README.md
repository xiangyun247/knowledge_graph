# Docker 配置文件说明

## 📁 文件结构

```
docker/
├── Dockerfile.backend    # 后端服务 Dockerfile
├── Dockerfile.celery     # Celery Worker Dockerfile
└── .dockerignore         # Docker 构建忽略文件
```

## 🐳 Dockerfile 说明

### Dockerfile.backend
- 用于构建 FastAPI 后端服务
- 基于 Python 3.9-slim
- 包含所有后端依赖
- 暴露端口 5001

### Dockerfile.celery
- 用于构建 Celery Worker
- 基于 Python 3.9-slim
- 包含 Celery 和 Redis 依赖
- 用于异步任务处理

## 🚀 使用方法

### 构建镜像

```bash
# 构建后端镜像
docker build -f docker/Dockerfile.backend -t kg-backend .

# 构建 Celery 镜像
docker build -f docker/Dockerfile.celery -t kg-celery .
```

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


