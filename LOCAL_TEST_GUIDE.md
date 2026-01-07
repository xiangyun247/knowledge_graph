# 本地测试指南 - 批量构建知识图谱

## 前置条件

1. ✅ Docker Desktop 正在运行
2. ✅ Hadoop 容器正常运行（hadoop-namenode 等）
3. ✅ Neo4j、MySQL、Redis 容器正常运行
4. ✅ Python 虚拟环境已激活，依赖已安装

## 启动本地后端服务

### 方法 1：使用 run.py（推荐）

```powershell
# 激活虚拟环境
cd "C:\Users\23035\PycharmProjects\knowledge_gragh"
.\venv\Scripts\Activate.ps1

# 启动后端服务（默认端口 8000）
python run.py
```

### 方法 2：直接使用 uvicorn

```powershell
# 激活虚拟环境
cd "C:\Users\23035\PycharmProjects\knowledge_gragh"
.\venv\Scripts\Activate.ps1

# 启动后端服务（指定端口 5001，与 Docker 后端一致）
uvicorn backend.app:app --host 0.0.0.0 --port 5001 --reload
```

## 配置检查

确保 `.env` 文件中包含以下配置：

```env
# Neo4j 配置（必须与 docker-compose.yml 中的密码一致）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=a2303548451

# DeepSeek API（用于知识图谱构建）
DEEPSEEK_API_KEY=your-api-key

# MySQL 配置（如果需要）
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=kg_user
MYSQL_PASSWORD=kg_password
MYSQL_DATABASE=knowledge_graph

# Redis 配置（Celery 需要）
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 测试步骤

### 1. 检查服务状态

```powershell
# 检查 Docker 容器
docker-compose ps

# 检查后端服务是否启动
curl http://localhost:5001/docs
# 或访问浏览器: http://localhost:5001/docs
```

### 2. 测试批量上传 API

使用 Postman 或浏览器访问 Swagger UI：
- 地址：`http://localhost:5001/docs`
- 找到 `POST /api/hadoop/upload/batch`
- 上传 1-2 个 PDF 文件
- 获取返回的 `uploaded_file_ids`

### 3. 测试批量构建 API

- 找到 `POST /api/hadoop/build/batch`
- 传入上一步获取的 `file_ids`
- 获取返回的 `task_id`

### 4. 查询任务状态

- 找到 `GET /api/hadoop/status/{task_id}`
- 使用上一步获取的 `task_id` 查询状态
- 观察 `status`、`progress`、`message` 的变化

### 5. 使用测试脚本（推荐）

```powershell
# 修改 tests/test_batch_build.py 中的 PDF 文件路径
# 然后运行：
python tests/test_batch_build.py
```

## 注意事项

1. **端口冲突**：
   - 如果 Docker 后端容器也在运行（端口 5001），需要先停止它：
     ```powershell
     docker-compose stop backend
     ```

2. **Docker 命令执行**：
   - 本地后端会通过 `docker exec hadoop-namenode` 执行 Hadoop 命令
   - 确保 Docker Desktop 正在运行，且能执行 `docker` 命令

3. **Neo4j 连接**：
   - 本地后端连接到 `localhost:7687`（Docker 容器的端口映射）
   - 确保 Neo4j 容器正常运行且密码正确

4. **Celery 任务**：
   - 如果使用 Celery 处理任务，确保 Redis 容器正常运行
   - Celery Worker 可以在 Docker 中运行，本地后端可以提交任务到 Redis

## 常见问题

### 问题 1：无法连接 Neo4j
- 检查 Neo4j 容器是否运行：`docker ps | Select-String neo4j`
- 检查密码是否一致：`.env` 和 `docker-compose.yml` 中的密码
- 检查端口映射：`docker-compose ps neo4j`

### 问题 2：无法执行 docker exec
- 检查 Docker Desktop 是否运行
- 检查 hadoop-namenode 容器是否运行：`docker ps | Select-String hadoop`
- 测试命令：`docker exec hadoop-namenode hadoop version`

### 问题 3：端口被占用
- 检查端口占用：`netstat -ano | findstr :5001`
- 停止占用端口的进程，或修改后端端口

## 下一步

测试成功后，可以：
1. 继续优化 Hadoop 集成逻辑
2. 完善错误处理和日志
3. 构建 Docker 后端镜像（如果需要）

