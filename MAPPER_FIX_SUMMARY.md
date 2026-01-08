# Mapper 脚本执行失败修复总结

## 问题描述

测试脚本 `test_batch_build_v2.py` 运行时遇到 mapper 脚本执行失败的问题：
- 错误信息：`PipeMapRed.waitOutputThreads(): subprocess failed with code 2`
- 根本原因：pdfplumber 0.5.0 版本存在兼容性问题，导致 `TypeError: startswith first arg must be str or a tuple of str, not bytes`

## 根本原因

1. **pdfplumber 版本过旧**：Dockerfile 中安装的是 pdfplumber 0.5.0，该版本在 Python 3.9 中存在兼容性问题
2. **错误信息截断**：mapper 脚本的错误处理逻辑不够健壮，导致错误信息被截断（如 `error='ID'`）

## 修复内容

### 1. 修复 mapper 脚本错误处理逻辑

**文件**：`hadoop/mapreduce/pdf_extract/mapper.py`

**改进点**：
- 改进了错误信息的提取逻辑，确保错误信息完整记录
- 添加了异常保护，确保即使异常对象有问题也能记录错误
- 限制错误信息长度，避免日志过长

**关键代码变更**：
```python
# 修复前：
error_msg = str(pdf_error) or repr(pdf_error)

# 修复后：
try:
    error_msg = str(pdf_error) if pdf_error else ""
    if not error_msg:
        error_msg = repr(pdf_error) if pdf_error else ""
    if not error_msg or len(error_msg) < 3:
        error_msg = f"{error_type} exception occurred"
except Exception:
    error_msg = f"{error_type} exception occurred (unable to get message)"
```

### 2. 升级 pdfplumber 库

**文件**：`docker/Dockerfile.hadoop-nodemanager-python`

**改进点**：
- 将 pdfplumber 从 0.5.0 升级到 >=0.11.0
- 新版本修复了 Python 3.9 兼容性问题

**关键代码变更**：
```dockerfile
# 修复前：
six pdfplumber==0.5.0

# 修复后：
six pdfplumber>=0.11.0
```

### 3. 运行时升级 pdfplumber

**操作**：
```bash
docker exec hadoop-nodemanager pip3 install --upgrade pdfplumber
```

**结果**：
- pdfplumber 从 0.5.0 升级到 0.11.8
- mapper 脚本可以正常处理 PDF 文件

## 验证方法

### 1. 测试 mapper 脚本

```bash
# 复制 mapper 脚本到容器
docker cp hadoop/mapreduce/pdf_extract/mapper.py hadoop-nodemanager:/tmp/test_mapper.py

# 测试执行
echo "/knowledge_graph/uploads/xxx/file.pdf" | docker exec -i hadoop-nodemanager /usr/local/bin/python3 /tmp/test_mapper.py
```

**预期结果**：
- PDF 文件可以正常提取文本
- 没有 `TypeError` 错误

### 2. 运行完整测试

```bash
python tests/test_batch_build_v2.py
```

**预期结果**：
- Hadoop 处理成功
- 任务状态为 `completed`
- 没有 mapper 脚本执行失败的错误

## 后续步骤

### 1. 重新构建 Docker 镜像（推荐）

为了确保修复持久化，建议重新构建 Docker 镜像：

```bash
docker-compose build hadoop-nodemanager
docker-compose up -d hadoop-nodemanager
```

### 2. 或者使用运行时升级（临时方案）

如果不想重新构建镜像，可以在容器启动后升级：

```bash
docker exec hadoop-nodemanager pip3 install --upgrade pdfplumber
```

**注意**：这种方式在容器重启后会失效，需要每次启动后都执行。

## 相关文件

- `hadoop/mapreduce/pdf_extract/mapper.py` - Mapper 脚本，包含错误处理逻辑
- `docker/Dockerfile.hadoop-nodemanager-python` - NodeManager Dockerfile，包含 pdfplumber 安装
- `tests/test_batch_build_v2.py` - 测试脚本

## 修复日期

2026年1月7日

