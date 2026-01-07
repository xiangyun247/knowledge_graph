# Hadoop Docker 镜像设置指南

## 📋 概述

本项目使用自定义的 Hadoop Docker 镜像，这些镜像基于官方 Hadoop 镜像，并添加了 Python 3 和 pdfplumber 支持，用于运行 MapReduce Python 脚本。

## 🐳 自定义镜像说明

### 为什么需要自定义镜像？

Hadoop 官方镜像（`bde2020/hadoop-namenode`）默认不包含 Python，而我们的 MapReduce 任务需要使用 Python 脚本来处理 PDF 文件。因此，我们创建了自定义镜像来添加：

1. **Python 3.5.3** - Debian 9 (stretch) 默认的 Python 版本
2. **pip3** - Python 包管理器
3. **pdfplumber 0.5.0** - PDF 文本提取库（兼容 Python 3.5）
4. **ImageMagick** - pdfplumber 的依赖库

### 镜像列表

| 镜像 | 基础镜像 | 用途 |
|------|---------|------|
| `hadoop-namenode-python` | `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8` | NameNode，运行 MapReduce 任务 |
| `hadoop-datanode-python` | `bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8` | DataNode，运行 MapReduce 任务 |

## 🔧 构建镜像

### 方式一：使用 Docker Compose（推荐）

```bash
# 构建所有镜像（包括 Hadoop 自定义镜像）
docker-compose build

# 或者只构建 Hadoop 镜像
docker-compose build hadoop-namenode hadoop-datanode
```

### 方式二：手动构建

```bash
# 构建 NameNode 镜像
docker build -f docker/Dockerfile.hadoop-python -t hadoop-namenode-python .

# 构建 DataNode 镜像
docker build -f docker/Dockerfile.hadoop-datanode-python -t hadoop-datanode-python .
```

## 🚀 使用自定义镜像

### 更新 docker-compose.yml

`docker-compose.yml` 已经配置为使用自定义构建的镜像：

```yaml
hadoop-namenode:
  build:
    context: .
    dockerfile: docker/Dockerfile.hadoop-python
  # ...

hadoop-datanode:
  build:
    context: .
    dockerfile: docker/Dockerfile.hadoop-datanode-python
  # ...
```

### 启动服务

```bash
# 启动所有服务（会自动构建镜像）
docker-compose up -d

# 或者先构建再启动
docker-compose build
docker-compose up -d
```

## ✅ 验证安装

### 检查 Python 是否安装

```bash
# 检查 NameNode 容器
docker exec hadoop-namenode python3 --version
# 应该输出: Python 3.5.3

# 检查 DataNode 容器
docker exec hadoop-datanode python3 --version
# 应该输出: Python 3.5.3
```

### 检查 pdfplumber 是否安装

```bash
# 检查 NameNode 容器
docker exec hadoop-namenode python3 -c "import pdfplumber; print('pdfplumber OK')"
# 应该输出: pdfplumber OK

# 检查 DataNode 容器
docker exec hadoop-datanode python3 -c "import pdfplumber; print('pdfplumber OK')"
# 应该输出: pdfplumber OK
```

## 🔍 故障排查

### 问题 1: 构建失败 - Debian 源不可用

**症状：** `404 Not Found` 或 `Failed to fetch`

**原因：** Debian 9 (stretch) 已停止维护，官方源已迁移到存档源

**解决方案：** Dockerfile 已经配置了存档源，如果仍然失败，检查网络连接或使用代理。

### 问题 2: pdfplumber 安装失败

**症状：** `ImportError` 或 `SyntaxError: invalid syntax`

**原因：** 
- Python 3.5 不支持 f-string（Python 3.6+ 特性）
- pdfplumber 新版本使用了 f-string

**解决方案：** Dockerfile 已经使用 `pdfplumber==0.5.0`，这是兼容 Python 3.5 的版本。

### 问题 3: ImageMagick 缺失

**症状：** `ImportError: MagickWand shared library not found`

**原因：** ImageMagick 库未安装

**解决方案：** Dockerfile 已经包含 `libmagickwand-dev` 的安装。

### 问题 4: 容器重启后依赖丢失

**症状：** 容器重启后 Python 或 pdfplumber 不可用

**原因：** 如果使用 `docker exec` 手动安装的依赖，容器重启后会丢失

**解决方案：** 使用自定义 Dockerfile 构建镜像，依赖会持久化。

## 📝 更新依赖

如果需要更新 Python 依赖（例如更新 pdfplumber 版本），需要：

1. 修改 `docker/Dockerfile.hadoop-python` 和 `docker/Dockerfile.hadoop-datanode-python`
2. 重新构建镜像：
   ```bash
   docker-compose build hadoop-namenode hadoop-datanode
   ```
3. 重启容器：
   ```bash
   docker-compose up -d --force-recreate hadoop-namenode hadoop-datanode
   ```

## 🎯 最佳实践

1. **使用 Dockerfile 而不是手动安装** - 确保依赖持久化
2. **版本锁定** - 使用固定版本的依赖（如 `pdfplumber==0.5.0`）
3. **定期更新** - 检查并更新基础镜像和依赖版本
4. **测试验证** - 构建后运行测试确保一切正常

## 📚 相关文档

- [Hadoop 集成测试指南](HADOOP_TESTING_GUIDE.md)
- [Hadoop 问题解决记录](HADOOP_ISSUES_RESOLVED.md)
- [Docker 配置文件说明](docker/README.md)

---

**最后更新：** 2026年1月  
**状态：** 已配置并测试通过

