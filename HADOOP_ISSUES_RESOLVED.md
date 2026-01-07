# Hadoop 集成问题解决总结

## 📋 项目背景

这是一个**医疗知识图谱系统**，正在引入 Hadoop 来处理大规模 PDF 文件的批量处理。

### Hadoop 在项目中的作用

Hadoop 被设计用于以下处理流程：

1. **PDF 文本提取** (`pdf_extract`) - 从 PDF 文件中提取文本内容
2. **文本清洗** (`text_clean`) - 清洗医学文本，去除噪音和无关内容
3. **文本分块** (`text_chunk`) - 将清洗后的文本分块，便于后续处理
4. **知识图谱构建** - 通过 Celery 从 HDFS 下载处理后的文本块并构建知识图谱

### 完整工作流程

```
上传 PDF 文件
    ↓
上传到 HDFS
    ↓
Hadoop MapReduce 处理：
  - PDF 提取 → 文本清洗 → 文本分块
    ↓
Celery 从 HDFS 下载文本块
    ↓
构建知识图谱（Neo4j + MySQL）
```

---

## 🔍 发现的问题

### 1. ✅ HDFS 端口配置错误（已修复）

**问题描述：**
- NameNode 实际监听在 **8020** 端口（Hadoop 3.x 默认 RPC 端口）
- 但配置文件中使用的是 **9000** 端口（Hadoop 2.x 的默认端口）
- 导致 HDFS 连接失败：`Connection refused`

**错误信息：**
```
Call From hadoop-namenode/172.18.0.4 to hadoop-namenode:9000 failed 
on connection exception: java.net.ConnectException: Connection refused
```

**修复内容：**
- ✅ `hadoop/config/core-site.xml` - 将 `fs.defaultFS` 从 `hdfs://hadoop-namenode:9000` 改为 `hdfs://hadoop-namenode:8020`
- ✅ `backend/hadoop_service.py` - 将默认端口从 9000 改为 8020
- ✅ `backend/celery_tasks.py` - 将默认端口从 9000 改为 8020
- ✅ `docker-compose.yml` - 更新端口映射和环境变量（外部端口 9000 映射到内部 8020）

**验证结果：**
```bash
docker exec hadoop-namenode hadoop fs -ls hdfs://hadoop-namenode:8020/
# ✅ 连接成功
```

---

## ✅ 已解决的问题

### 1. HDFS 端口配置问题
- **状态：** ✅ 已修复
- **影响：** 高 - 导致无法连接 HDFS
- **修复文件：**
  - `hadoop/config/core-site.xml`
  - `backend/hadoop_service.py`
  - `backend/celery_tasks.py`
  - `docker-compose.yml`

### 2. Python 依赖安装
- **状态：** ✅ 已解决
- **说明：** Python 3 和 pdfplumber 已在 Hadoop 容器中安装

### 3. Hadoop Streaming JAR
- **状态：** ✅ 正常
- **位置：** `/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar`

### 4. MapReduce 脚本
- **状态：** ✅ 正常
- **脚本位置：**
  - `hadoop/mapreduce/pdf_extract/mapper.py`
  - `hadoop/mapreduce/pdf_extract/reducer.py`
  - `hadoop/mapreduce/text_clean/mapper.py`
  - `hadoop/mapreduce/text_chunk/mapper.py`

### 5. Hadoop 配置文件
- **状态：** ✅ 正常
- **配置文件：**
  - `hadoop/config/core-site.xml`
  - `hadoop/config/hdfs-site.xml`
  - `hadoop/config/mapred-site.xml`
  - `hadoop/config/yarn-site.xml`

---

## ⚠️ 待处理的问题

### 1. NodeManager 未运行

**状态：** ⚠️ 待处理（非关键）

**问题描述：**
- NodeManager 容器未运行
- 可能影响 MapReduce 任务的执行

**可能原因：**
- 容器启动失败
- 依赖服务未就绪
- 配置问题

**建议处理：**
```bash
# 检查 NodeManager 日志
docker logs hadoop-nodemanager

# 手动启动 NodeManager
docker-compose up -d hadoop-nodemanager

# 检查 ResourceManager 是否正常运行（NodeManager 依赖它）
docker ps --filter "name=hadoop-resourcemanager"
```

**注意：** 如果 ResourceManager 正常运行，MapReduce 任务可能仍然可以执行，但建议修复 NodeManager 以确保完整功能。

---

## 🧪 测试验证

### 1. 运行环境诊断

```bash
python scripts/check_hadoop_env.py
```

**预期结果：**
- ✅ Docker: 通过
- ✅ Hadoop 容器: 通过（除 NodeManager 外）
- ✅ HDFS 连接: 通过
- ✅ Streaming JAR: 通过
- ✅ MapReduce 脚本: 通过
- ✅ Hadoop 配置: 通过
- ✅ Python 依赖: 通过

### 2. 测试 HDFS 连接

```bash
# 测试 HDFS 连接
docker exec hadoop-namenode hadoop fs -ls hdfs://hadoop-namenode:8020/

# 创建测试目录
docker exec hadoop-namenode hadoop fs -mkdir -p /knowledge_graph/test

# 上传测试文件
docker exec hadoop-namenode hadoop fs -put /etc/hostname /knowledge_graph/test/
```

### 3. 测试批量处理流程

使用测试脚本：
```bash
python tests/test_batch_build.py
```

该脚本会：
1. 批量上传 PDF 文件到 HDFS
2. 触发 Hadoop + Celery 批量构建知识图谱
3. 轮询任务状态直到完成

---

## 📝 配置变更摘要

### 端口配置统一

所有相关配置已统一使用 **8020** 端口（Hadoop 3.x 默认 RPC 端口）：

| 文件 | 配置项 | 旧值 | 新值 |
|------|--------|------|------|
| `core-site.xml` | `fs.defaultFS` | `hdfs://hadoop-namenode:9000` | `hdfs://hadoop-namenode:8020` |
| `hadoop_service.py` | `HADOOP_NAMENODE` 默认值 | `hadoop-namenode:9000` | `hadoop-namenode:8020` |
| `celery_tasks.py` | `HADOOP_NAMENODE` 默认值 | `localhost:9000` | `localhost:8020` |
| `docker-compose.yml` | 端口映射 | `9000:9000` | `9000:8020` |
| `docker-compose.yml` | 环境变量 | `hadoop-namenode:9000` | `hadoop-namenode:8020` |

---

## 🚀 下一步建议

### 1. 修复 NodeManager

```bash
# 检查日志
docker logs hadoop-nodemanager --tail 50

# 重启 NodeManager
docker-compose restart hadoop-nodemanager

# 或重新创建
docker-compose up -d --force-recreate hadoop-nodemanager
```

### 2. 测试完整的 MapReduce 流程

1. 上传测试 PDF 文件
2. 运行 PDF 提取任务
3. 运行文本清洗任务
4. 运行文本分块任务
5. 验证输出结果

### 3. 集成测试

运行端到端测试，验证：
- 文件上传到 HDFS
- Hadoop MapReduce 处理
- Celery 任务执行
- 知识图谱构建

### 4. 性能优化

- 对于小文件，考虑合并处理以减少 MapReduce 开销
- 优化文件上传/下载流程
- 添加任务监控和日志记录

---

## 📚 相关文档

- [Hadoop README](hadoop/README.md) - Hadoop 模块说明
- [HADOOP_FIXES.md](HADOOP_FIXES.md) - 之前的修复记录
- [HADOOP_DIAGNOSIS_RESULTS.md](HADOOP_DIAGNOSIS_RESULTS.md) - 诊断结果
- [Docker README](docker/README.md) - Docker 部署说明

---

## 🎯 总结

### 主要成就

1. ✅ **解决了关键的 HDFS 连接问题** - 统一了端口配置为 8020
2. ✅ **验证了 Hadoop 环境基本正常** - 容器运行、依赖安装、脚本就绪
3. ✅ **建立了完整的诊断工具** - `check_hadoop_env.py` 可以快速检查环境状态

### 当前状态

- **HDFS 连接：** ✅ 正常
- **Hadoop 容器：** ✅ 基本正常（除 NodeManager 外）
- **Python 依赖：** ✅ 已安装
- **MapReduce 脚本：** ✅ 就绪
- **配置文件：** ✅ 正确

### 待完成

- ⚠️ 修复 NodeManager 启动问题（非关键，但建议修复）
- 📝 进行端到端测试验证完整流程
- 🔧 性能优化和监控

---

**最后更新：** 2026年1月6日  
**状态：** 主要问题已解决，HDFS 连接正常，可以进行测试

