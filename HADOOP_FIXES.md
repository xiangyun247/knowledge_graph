# Hadoop 集成问题修复总结

## 📋 问题概述

本次修复解决了项目在引入 Hadoop 时遇到的多个配置和集成问题。

## 🔍 发现的问题

### 1. ✅ 配置文件重复和冲突（已修复）

**问题描述：**
- `core-site.xml`: 存在多个 `fs.defaultFS` 配置，值冲突（9000 vs 8020）
- `hdfs-site.xml`: 存在重复的配置项
- `yarn-site.xml`: 有大量重复的 `bind-host` 配置（约70行重复）
- `mapred-site.xml`: 有重复配置项

**修复内容：**
- 清理了所有配置文件中的重复项
- 统一了端口配置（使用 9000 端口，与 docker-compose.yml 一致）
- 保留了必要的 Docker 环境配置（bind-host）

### 2. ✅ Hadoop Streaming 路径问题（已修复）

**问题描述：**
- JAR 文件路径硬编码，可能在不同环境中找不到
- 没有动态查找机制

**修复内容：**
- 在 `HadoopService` 中添加了 `_find_streaming_jar()` 方法
- 支持多个可能的路径自动查找
- 添加了日志记录，便于调试

### 3. ✅ MapReduce Mapper 脚本问题（已修复）

**问题描述：**
- PDF 提取 mapper 从环境变量读取文件路径，在 Hadoop Streaming 中可能不可靠
- 错误处理不完善

**修复内容：**
- 修改为从标准输入读取文件路径列表（符合 Hadoop Streaming 规范）
- 改进了错误处理和日志记录
- 确保每个文件处理失败时不影响其他文件

### 4. ✅ HDFS 客户端连接问题（已修复）

**问题描述：**
- 在 Docker 环境下，hdfs3 库可能无法直接连接
- 缺少 Docker 环境的适配

**修复内容：**
- 优化了 `HDFSClient`，优先使用 Docker 方式（`docker exec`）
- 改进了文件上传/下载逻辑，使用容器临时目录作为中转
- 保持向后兼容（支持非 Docker 环境）

### 5. ✅ 环境检查和测试脚本（已创建）

**新增内容：**
- 创建了 `scripts/check_hadoop_env.py` 诊断脚本
- 可以检查：
  - Docker 环境
  - Hadoop 容器状态
  - HDFS 连接
  - Streaming JAR 路径
  - Python 依赖
  - MapReduce 脚本
  - 配置文件

## 📝 修复的文件列表

1. **配置文件：**
   - `hadoop/config/core-site.xml`
   - `hadoop/config/hdfs-site.xml`
   - `hadoop/config/yarn-site.xml`
   - `hadoop/config/mapred-site.xml`

2. **核心代码：**
   - `backend/hadoop_service.py` - 添加了 Streaming JAR 动态查找
   - `hadoop/utils/hdfs_client.py` - 优化了 Docker 环境支持
   - `hadoop/mapreduce/pdf_extract/mapper.py` - 修复了输入处理逻辑

3. **新增文件：**
   - `scripts/check_hadoop_env.py` - 环境诊断脚本

## 🚀 使用指南

### 1. 运行环境检查

```bash
python scripts/check_hadoop_env.py
```

这个脚本会检查所有 Hadoop 相关的环境配置，输出详细的诊断信息。

### 2. 启动 Hadoop 服务

确保 Docker 容器正在运行：

```bash
docker-compose up -d hadoop-namenode hadoop-datanode hadoop-resourcemanager hadoop-nodemanager
```

### 3. 验证 HDFS 连接

```bash
# 查看 HDFS 根目录
docker exec hadoop-namenode hadoop fs -ls /

# 创建测试目录
docker exec hadoop-namenode hadoop fs -mkdir -p /knowledge_graph/test

# 上传测试文件
docker exec hadoop-namenode hadoop fs -put /etc/hostname /knowledge_graph/test/
```

### 4. 运行 MapReduce 任务

通过 API 或直接调用 `HadoopService`：

```python
from backend.hadoop_service import get_hadoop_service

hadoop_service = get_hadoop_service()

# 处理文件
result = hadoop_service.process_files_with_hadoop(file_ids=["file1", "file2"])
```

## ⚠️ 注意事项

### 1. Python 依赖

MapReduce 脚本需要以下 Python 库（需要在 Hadoop 容器中安装）：

```bash
# 进入 Hadoop 容器
docker exec -it hadoop-namenode bash

# 安装依赖
pip install pdfplumber

# 或通过 Dockerfile 在构建时安装
```

### 2. 文件路径

- 本地文件路径在 Windows 和 Linux 之间可能有差异
- 代码中已处理了路径转换（通过 Docker 临时目录中转）

### 3. 权限问题

- 确保 Docker 容器有足够权限访问 HDFS
- 如果是 Windows，可能需要配置 Docker Desktop 的文件共享权限

### 4. 网络配置

- Hadoop 容器需要能够相互通信
- 确保 `docker-compose.yml` 中的网络配置正确

## 🔧 后续优化建议

1. **创建 Dockerfile 安装 Python 依赖**
   - 在 Hadoop 容器中预装 pdfplumber 等库
   - 避免每次运行任务时安装

2. **改进错误处理**
   - 添加更详细的错误信息和日志
   - 支持任务重试机制

3. **性能优化**
   - 对于小文件，考虑合并处理以减少 MapReduce 开销
   - 优化文件上传/下载流程

4. **监控和调试**
   - 集成 Hadoop Web UI（NameNode: 9870, ResourceManager: 8088）
   - 添加任务执行监控

5. **测试覆盖**
   - 创建单元测试和集成测试
   - 测试不同场景下的错误处理

## 📚 相关文档

- [Hadoop README](hadoop/README.md) - Hadoop 模块说明
- [Docker README](docker/README.md) - Docker 部署说明
- [HADOOP_INTEGRATION_PLAN.md](HADOOP_INTEGRATION_PLAN.md) - 集成计划（如果存在）

## 🐛 常见问题

### Q: 容器启动失败？
A: 检查 Docker 是否运行，端口是否被占用（9870, 9000, 8088, 8042）

### Q: HDFS 连接超时？
A: 检查容器网络配置，确保容器在同一网络中

### Q: MapReduce 任务失败？
A: 
1. 检查 Python 依赖是否安装
2. 查看容器日志：`docker logs hadoop-namenode`
3. 检查脚本路径是否正确
4. 运行诊断脚本：`python scripts/check_hadoop_env.py`

### Q: 文件上传失败？
A: 
1. 检查本地文件是否存在
2. 检查 HDFS 权限
3. 查看 Docker 日志

---

**修复完成时间：** 2025年1月  
**版本：** v1.1.0

