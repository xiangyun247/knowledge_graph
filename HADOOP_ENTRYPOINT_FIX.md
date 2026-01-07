# Hadoop Entrypoint 修复说明

## 问题描述

容器启动后立即退出（退出码 0），日志显示 entrypoint 执行完成但容器没有保持运行。

## 问题原因

1. 自定义 entrypoint 脚本使用了 `set -e`，导致任何错误都会立即退出
2. 原始 entrypoint 期望接收命令参数（`exec $@`），但 docker-compose 中没有指定 CMD，导致 `$@` 为空
3. 当 `$@` 为空时，`exec` 没有参数，容器执行完 entrypoint 后退出

## 修复内容

### 1. 移除 `set -e`
- 允许清理过程中的错误不影响容器启动
- 确保即使清理失败也能继续执行原始 entrypoint

### 2. 添加默认命令处理
- 当没有传递命令参数时，自动使用 `/run.sh`（基础镜像的默认 CMD）
- 确保容器能够正常启动并保持运行

### 3. 改进错误处理
- 添加更详细的错误信息
- 在找不到原始 entrypoint 时提供备选方案

## 修复后的工作流程

1. **清理配置**：执行清理脚本，移除重复配置项
2. **查找原始 entrypoint**：查找并备份原始 entrypoint 脚本
3. **执行原始 entrypoint**：
   - 如果有参数，传递参数执行
   - 如果没有参数，使用默认的 `/run.sh`
4. **保持容器运行**：原始 entrypoint 会启动 Hadoop 服务并保持容器运行

## 测试步骤

1. **重新构建镜像**：
   ```bash
   docker-compose build hadoop-namenode hadoop-datanode
   ```

2. **启动容器**：
   ```bash
   docker-compose up -d hadoop-namenode hadoop-datanode
   ```

3. **检查容器状态**：
   ```bash
   docker ps | findstr hadoop
   ```

4. **查看日志**：
   ```bash
   docker logs hadoop-namenode
   docker logs hadoop-datanode
   ```

5. **验证服务**：
   ```bash
   # 检查 NameNode Web UI
   curl http://localhost:9870
   
   # 检查 DataNode Web UI
   curl http://localhost:9864
   ```

## 预期结果

- 容器应该保持运行状态（`Up` 状态）
- 日志中应该看到：
  - "Cleaning Hadoop configuration files to remove duplicates..."
  - "Configuration cleanup completed."
  - "Executing original entrypoint: /original-entrypoint.sh"
  - "No command provided, using default: /run.sh"
  - Hadoop 服务启动日志

## 注意事项

1. 如果容器仍然退出，检查：
   - 日志中的错误信息
   - 配置文件是否正确
   - 原始 entrypoint 是否存在

2. 如果清理失败，容器仍会尝试启动，但可能会有重复配置问题

3. 对于官方镜像容器（resourcemanager, nodemanager），仍然需要使用清理脚本手动清理

