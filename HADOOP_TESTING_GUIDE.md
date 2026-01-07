# Hadoop 集成测试指南

## 📋 测试前准备

### 1. 确保所有服务运行

```bash
# 检查 Docker 容器状态
docker ps

# 应该看到以下容器运行中：
# - hadoop-namenode
# - hadoop-datanode
# - hadoop-resourcemanager
# - hadoop-nodemanager (可选，但建议运行)
# - kg-redis
# - kg-neo4j
# - kg-mysql
# - kg-backend (如果使用 Docker)
# - kg-celery-worker (如果使用 Docker)
```

### 2. 确保后端服务运行

如果使用本地运行（非 Docker）：
```bash
# 在项目根目录
python run.py
# 或
uvicorn backend.app:app --host 0.0.0.0 --port 5001
```

## 🧪 测试步骤

### 步骤 1: 运行基础集成测试

```bash
python scripts/test_hadoop_integration.py
```

这个脚本会测试：
- ✅ HDFS 基本操作（创建目录、上传文件、读取文件）
- ✅ MapReduce 脚本上传功能
- ✅ Hadoop 服务初始化
- ✅ Celery 集成检查

### 步骤 2: 运行完整端到端测试

#### 方式 A: 使用测试脚本（推荐）

1. **准备测试 PDF 文件**
   - 将测试 PDF 文件放在 `data/raw/` 目录
   - 或修改 `tests/test_batch_build.py` 中的 `PDF_FILES` 路径

2. **运行测试脚本**
   ```bash
   python tests/test_batch_build.py
   ```

   这个脚本会：
   - 批量上传 PDF 文件到后端和 HDFS
   - 触发 Hadoop MapReduce 处理（PDF提取 → 文本清洗 → 文本分块）
   - 触发 Celery 任务构建知识图谱
   - 轮询任务状态直到完成

#### 方式 B: 使用 API 手动测试

1. **批量上传文件**
   ```bash
   curl -X POST "http://localhost:5001/api/hadoop/upload/batch" \
     -F "files=@/path/to/test1.pdf" \
     -F "files=@/path/to/test2.pdf"
   ```

   或使用 Python：
   ```python
   import requests
   
   files = [
       ('files', ('test1.pdf', open('test1.pdf', 'rb'), 'application/pdf')),
       ('files', ('test2.pdf', open('test2.pdf', 'rb'), 'application/pdf')),
   ]
   
   response = requests.post(
       'http://localhost:5001/api/hadoop/upload/batch',
       files=files
   )
   print(response.json())
   ```

2. **触发批量构建**
   ```bash
   curl -X POST "http://localhost:5001/api/hadoop/build/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "file_ids": ["file-id-1", "file-id-2"],
       "use_hadoop": true
     }'
   ```

3. **查询任务状态**
   ```bash
   curl "http://localhost:5001/api/hadoop/status/{task_id}"
   ```

### 步骤 3: 验证处理结果

#### 检查 HDFS 中的处理结果

```bash
# 查看 PDF 提取结果
docker exec hadoop-namenode hadoop fs -ls /knowledge_graph/processed/pdf_extract

# 查看文本清洗结果
docker exec hadoop-namenode hadoop fs -ls /knowledge_graph/processed/text_clean

# 查看文本分块结果
docker exec hadoop-namenode hadoop fs -ls /knowledge_graph/processed/text_chunk

# 查看某个分块的内容
docker exec hadoop-namenode hadoop fs -cat /knowledge_graph/processed/text_chunk/part-00000 | head -20
```

#### 检查知识图谱构建结果

```bash
# 通过 API 查询图谱列表
curl "http://localhost:5001/api/kg/list"

# 查询特定图谱
curl "http://localhost:5001/api/kg/{graph_id}"

# 查看图谱可视化数据
curl "http://localhost:5001/api/kg/{graph_id}/visualize"
```

## 🔍 故障排查

### 问题 1: HDFS 连接失败

**症状：** `Connection refused` 或 `NameNode not found`

**解决方案：**
```bash
# 检查 NameNode 容器状态
docker ps --filter "name=hadoop-namenode"

# 检查 NameNode 日志
docker logs hadoop-namenode --tail 50

# 验证端口配置
docker exec hadoop-namenode cat /etc/hadoop/core-site.xml | grep fs.defaultFS
# 应该显示: hdfs://hadoop-namenode:8020
```

### 问题 2: MapReduce 任务失败

**症状：** 任务提交后立即失败或超时

**解决方案：**
```bash
# 检查 NodeManager 是否运行
docker ps --filter "name=hadoop-nodemanager"

# 检查 ResourceManager 日志
docker logs hadoop-resourcemanager --tail 50

# 检查 NodeManager 日志
docker logs hadoop-nodemanager --tail 50

# 验证 Python 和依赖
docker exec hadoop-namenode python3 --version
docker exec hadoop-namenode python3 -c "import pdfplumber; print('OK')"
```

### 问题 3: PDF 提取失败

**症状：** PDF 提取任务返回错误

**解决方案：**
```bash
# 检查 pdfplumber 是否安装
docker exec hadoop-namenode python3 -c "import pdfplumber"

# 如果未安装，安装它
docker exec hadoop-namenode pip3 install pdfplumber

# 或使用国内镜像源（更快）
docker exec hadoop-namenode pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple pdfplumber
```

### 问题 4: Celery 任务未执行

**症状：** Hadoop 处理完成但 Celery 任务未启动

**解决方案：**
```bash
# 检查 Redis 连接
docker exec kg-redis redis-cli ping

# 检查 Celery Worker 日志
docker logs kg-celery-worker --tail 50

# 检查 Celery Worker 是否运行
docker ps --filter "name=kg-celery-worker"
```

## 📊 监控和日志

### 查看 Hadoop Web UI

- **NameNode Web UI**: http://localhost:9870
- **ResourceManager Web UI**: http://localhost:8088
- **DataNode Web UI**: http://localhost:9864

### 查看应用日志

```bash
# 后端日志
tail -f logs/app.log

# Celery Worker 日志
docker logs -f kg-celery-worker

# Hadoop 容器日志
docker logs -f hadoop-namenode
docker logs -f hadoop-resourcemanager
```

## ✅ 成功标准

完整的端到端测试成功应该满足：

1. ✅ 文件成功上传到 HDFS
2. ✅ PDF 提取任务成功完成
3. ✅ 文本清洗任务成功完成
4. ✅ 文本分块任务成功完成
5. ✅ Celery 任务成功下载文本块
6. ✅ 知识图谱成功构建（有实体和关系）
7. ✅ 可以通过 API 查询到构建的图谱

## 🚀 下一步

测试通过后，你可以：

1. **优化性能**
   - 调整 MapReduce 任务参数
   - 优化文本分块大小
   - 调整 Celery Worker 并发数

2. **扩展功能**
   - 添加更多文本处理步骤
   - 优化医学文本清洗规则
   - 添加任务监控和告警

3. **生产部署**
   - 配置持久化存储
   - 设置资源限制
   - 配置日志轮转
   - 添加健康检查

---

**最后更新**: 2026年1月  
**状态**: 测试就绪

