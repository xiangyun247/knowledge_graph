# Hadoop 诊断和修复结果

## ✅ 已修复的问题

### 1. HDFS 端口配置问题
**问题：** 配置文件中使用 9000 端口，但 NameNode 实际运行在 8020 端口

**修复：**
- 修改 `hadoop/config/core-site.xml`，将 `fs.defaultFS` 改为 `hdfs://hadoop-namenode:8020`
- 更新 `backend/hadoop_service.py`，自动适配 8020 端口

**验证：**
```bash
docker exec hadoop-namenode hadoop fs -ls hdfs://hadoop-namenode:8020/
# ✓ 连接成功
```

### 2. Python 3 安装
**问题：** Hadoop 容器中缺少 Python 3

**修复：**
- 配置 Debian 存档源（Debian 9 已停止维护）
- 成功安装 Python 3.5.3 和 pip3

**验证：**
```bash
docker exec hadoop-namenode python3 --version
# Python 3.5.3
```

### 3. NodeManager 启动
**问题：** NodeManager 容器未运行

**修复：**
- 使用 `docker-compose up -d hadoop-nodemanager` 启动容器

## ⚠️ 待处理的问题

### 1. pdfplumber 安装超时
**状态：** 安装过程中网络超时

**解决方案：**
```bash
# 方案1：重试安装（可能需要多次尝试）
docker exec hadoop-namenode pip3 install pdfplumber

# 方案2：使用国内镜像源（更快）
docker exec hadoop-namenode pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple pdfplumber

# 方案3：使用超时参数
docker exec hadoop-namenode pip3 install --default-timeout=100 pdfplumber
```

### 2. NodeManager 状态检查
**建议：** 检查 NodeManager 是否正常运行
```bash
docker logs hadoop-nodemanager --tail 50
docker ps --filter "name=hadoop-nodemanager"
```

## 📋 重新运行诊断

修复配置和安装 Python 后，重新运行诊断脚本：

```bash
python scripts/check_hadoop_env.py
```

预期结果：
- ✅ Docker: 通过
- ✅ Hadoop 容器: 通过（包括 NodeManager）
- ✅ HDFS 连接: 通过（使用 8020 端口）
- ✅ Streaming JAR: 通过
- ✅ MapReduce 脚本: 通过
- ✅ Hadoop 配置: 通过
- ⚠️ Python 依赖: pdfplumber 可能仍显示未安装（需要重试安装）

## 🔧 快速修复命令

如果 pdfplumber 仍未安装，运行以下命令：

```bash
# 使用清华镜像源安装（推荐，更快）
docker exec hadoop-namenode pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple pdfplumber

# 验证安装
docker exec hadoop-namenode python3 -c "import pdfplumber; print('pdfplumber installed successfully')"
```

## 📝 配置文件更改摘要

1. **hadoop/config/core-site.xml**
   - 更改端口：`9000` → `8020`

2. **backend/hadoop_service.py**
   - 添加端口自动适配逻辑

3. **容器状态**
   - Python 3.5.3 已安装
   - pip3 已安装
   - 软件源已配置为 Debian 存档源

## 🚀 下一步

1. 完成 pdfplumber 安装
2. 验证 NodeManager 正常运行
3. 测试 MapReduce 任务（PDF 提取、文本清洗、文本分块）
4. 运行端到端测试

---

**更新时间：** 2025年1月6日  
**状态：** 主要问题已修复，部分依赖安装待完成

