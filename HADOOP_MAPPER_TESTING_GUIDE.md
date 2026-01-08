# Hadoop Mapper 脚本测试指南

## 概述

本指南帮助您测试和诊断 Hadoop MapReduce mapper 脚本的问题。

## 测试工具

### 1. 全面测试工具 (`scripts/test_mapper_comprehensive.py`)

这个工具会检查所有 mapper 脚本的：
- 文件是否存在
- 语法是否正确
- 依赖是否安装
- 基本功能是否正常

**使用方法：**
```bash
python scripts/test_mapper_comprehensive.py
```

**测试结果：**
- ✅ `text_clean` mapper: 通过
- ✅ `text_chunk` mapper: 通过
- ⚠️ `pdf_extract` mapper: 需要真实的 PDF 文件

### 2. Hadoop Streaming 任务测试 (`scripts/test_hadoop_streaming_job.py`)

这个工具会测试完整的 Hadoop Streaming 任务流程：
1. 创建测试数据
2. 上传到 HDFS
3. 提交 Hadoop Streaming 任务
4. 检查输出结果

**使用方法：**
```bash
python scripts/test_hadoop_streaming_job.py
```

### 3. 简单测试工具 (`scripts/test_mapper_on_nodemanager.py`)

这个工具在 NodeManager 容器中直接测试 mapper 脚本。

**使用方法：**
```bash
python scripts/test_mapper_on_nodemanager.py
```

## 当前状态

### ✅ 已通过的测试

1. **text_clean mapper**
   - 语法检查: ✅
   - 依赖检查: ✅
   - 功能测试: ✅

2. **text_chunk mapper**
   - 语法检查: ✅
   - 依赖检查: ✅
   - 功能测试: ✅

### ⚠️ 需要关注的测试

1. **pdf_extract mapper**
   - 语法检查: ✅
   - 依赖检查: ✅ (pdfplumber 已安装)
   - 功能测试: ⚠️ 需要真实的 PDF 文件

## 常见问题排查

### 问题 1: Mapper 脚本语法错误

**症状：**
```
[FAIL] 语法错误: ...
```

**解决方法：**
1. 检查脚本文件是否存在
2. 在容器中手动检查语法：
   ```bash
   docker exec hadoop-nodemanager python3 -m py_compile /path/to/mapper.py
   ```

### 问题 2: 缺少依赖

**症状：**
```
[FAIL] 缺少依赖: pdfplumber
```

**解决方法：**
在容器中安装依赖：
```bash
docker exec hadoop-nodemanager pip install pdfplumber
```

### 问题 3: Mapper 脚本执行失败

**症状：**
```
[FAIL] 执行失败: ...
```

**解决方法：**
1. 检查脚本是否有可执行权限
2. 检查 Python 环境是否正确
3. 查看详细的错误信息

### 问题 4: Hadoop Streaming 任务失败

**症状：**
任务提交后返回非零退出码

**解决方法：**
1. 检查 mapper 脚本路径是否正确
2. 检查输入数据是否存在
3. 检查输出目录是否可写
4. 查看 Hadoop 日志：
   ```bash
   docker exec hadoop-nodemanager cat /opt/hadoop-3.2.1/logs/userlogs/...
   ```

## 测试 PDF 提取 Mapper

要测试 `pdf_extract` mapper，需要：

1. **上传测试 PDF 文件到 HDFS：**
   ```bash
   # 准备一个 PDF 文件
   # 上传到 HDFS
   docker exec hadoop-namenode hadoop fs -put test.pdf /knowledge_graph/uploads/test/test.pdf
   ```

2. **运行测试：**
   ```bash
   python scripts/test_mapper_comprehensive.py
   ```

## 调试技巧

### 1. 手动测试 Mapper 脚本

在容器中直接运行 mapper 脚本：
```bash
# 复制脚本到容器
docker cp hadoop/mapreduce/text_clean/mapper.py hadoop-nodemanager:/tmp/mapper.py

# 在容器中运行
docker exec -i hadoop-nodemanager python3 /tmp/mapper.py < test_input.txt
```

### 2. 查看 Hadoop 任务日志

```bash
# 列出所有任务
docker exec hadoop-namenode yarn application -list

# 查看任务日志
docker exec hadoop-namenode yarn logs -applicationId <application_id>
```

### 3. 检查 HDFS 文件

```bash
# 列出文件
docker exec hadoop-namenode hadoop fs -ls /knowledge_graph/

# 查看文件内容
docker exec hadoop-namenode hadoop fs -cat /knowledge_graph/path/to/file
```

## 下一步

1. ✅ 所有 mapper 脚本语法正确
2. ✅ text_clean 和 text_chunk mapper 功能正常
3. ⚠️ 需要测试 pdf_extract mapper（需要真实 PDF 文件）
4. ⏳ 测试完整的 Hadoop 处理流程

## 相关文件

- `scripts/test_mapper_comprehensive.py`: 全面测试工具
- `scripts/test_hadoop_streaming_job.py`: Streaming 任务测试
- `scripts/test_mapper_on_nodemanager.py`: 简单测试工具
- `backend/hadoop_service.py`: Hadoop 服务封装
- `hadoop/mapreduce/`: Mapper 和 Reducer 脚本目录

## 测试结果文件

测试结果会自动保存到 `mapper_test_results.json`，包含详细的测试信息。

