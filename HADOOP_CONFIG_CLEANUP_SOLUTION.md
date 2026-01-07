# Hadoop 配置重复问题解决方案

## 问题描述

Hadoop 容器的 entrypoint 脚本在每次容器启动时会自动向配置文件追加配置，导致重复和错误的配置项。这会导致 Hadoop 服务无法正常启动或运行异常。

## 解决方案

我们提供了两种解决方案：

### 方案一：自定义 Entrypoint 脚本（推荐）

**适用于：** 自定义构建的容器（hadoop-namenode, hadoop-datanode）

**实现方式：**
1. 创建了自定义 entrypoint 脚本 `docker/hadoop-entrypoint.sh`
2. 该脚本在调用原始 entrypoint 之前自动清理重复配置
3. 修改了 Dockerfile 以使用自定义 entrypoint

**优点：**
- 自动执行，无需手动干预
- 在容器启动前清理，避免配置错误
- 完全透明，不影响原有功能

**使用方法：**
```bash
# 重新构建镜像
docker-compose build hadoop-namenode hadoop-datanode

# 启动容器
docker-compose up -d hadoop-namenode hadoop-datanode
```

### 方案二：自动清理脚本（备选方案）

**适用于：** 所有 Hadoop 容器，特别是使用官方镜像的容器（hadoop-resourcemanager, hadoop-nodemanager）

**实现方式：**
1. 创建了自动清理脚本 `scripts/auto_clean_hadoop_configs.py`
2. 可以在容器启动后自动或手动执行

**使用方法：**

#### 方法 A：手动执行（推荐用于官方镜像容器）
```bash
# 在容器启动后执行清理
python scripts/auto_clean_hadoop_configs.py

# 然后重启容器以应用清理后的配置
docker-compose restart hadoop-resourcemanager hadoop-nodemanager
```

#### 方法 B：在容器内执行（需要将脚本复制到容器）
```bash
# 将清理脚本复制到容器
docker cp scripts/clean_hadoop_configs_post_start.sh hadoop-namenode:/tmp/clean.sh

# 在容器内执行
docker exec hadoop-namenode bash /tmp/clean.sh
```

#### 方法 C：使用 docker-compose 的 command 覆盖（适用于官方镜像）
可以在 docker-compose.yml 中为官方镜像容器添加启动后清理命令，但这需要修改 entrypoint，可能比较复杂。

## 文件说明

### 核心文件

1. **`docker/hadoop-entrypoint.sh`**
   - 自定义 entrypoint 脚本
   - 在调用原始 entrypoint 前清理重复配置
   - 自动检测并调用原始 entrypoint

2. **`docker/Dockerfile.hadoop-python`**
   - NameNode 的 Dockerfile
   - 已配置使用自定义 entrypoint

3. **`docker/Dockerfile.hadoop-datanode-python`**
   - DataNode 的 Dockerfile
   - 已配置使用自定义 entrypoint

4. **`scripts/auto_clean_hadoop_configs.py`**
   - 自动清理脚本（Python）
   - 可以清理所有 Hadoop 容器的配置文件
   - 支持等待容器启动后自动清理

5. **`scripts/clean_hadoop_configs_post_start.sh`**
   - 容器内清理脚本（Bash）
   - 可以在容器内部执行
   - 使用 Python 3 进行 XML 解析和清理

### 现有清理脚本（保留）

- `scripts/clean_hadoop_config.py` - 原有的清理脚本
- `scripts/clean_container_configs.py` - 容器配置清理脚本

## 使用流程

### 首次部署

1. **构建自定义镜像**
   ```bash
   docker-compose build hadoop-namenode hadoop-datanode
   ```

2. **启动所有容器**
   ```bash
   docker-compose up -d
   ```

3. **清理官方镜像容器的配置（如果需要）**
   ```bash
   python scripts/auto_clean_hadoop_configs.py
   docker-compose restart hadoop-resourcemanager hadoop-nodemanager
   ```

### 容器重启后

**自定义镜像容器（namenode, datanode）：**
- 自动清理，无需手动操作

**官方镜像容器（resourcemanager, nodemanager）：**
- 如果发现重复配置，运行：
  ```bash
  python scripts/auto_clean_hadoop_configs.py
  docker-compose restart hadoop-resourcemanager hadoop-nodemanager
  ```

## 验证配置

检查配置文件是否正确：

```bash
# 检查容器内的配置文件
docker exec hadoop-namenode cat /etc/hadoop/core-site.xml
docker exec hadoop-datanode cat /etc/hadoop/hdfs-site.xml
```

配置文件应该：
- 每个属性只出现一次
- XML 格式正确
- 没有重复的单行格式配置

## 故障排除

### 问题：自定义 entrypoint 不工作

**检查：**
1. 确认 Dockerfile 已正确复制 entrypoint 脚本
2. 确认 entrypoint 脚本有执行权限
3. 查看容器日志：`docker logs hadoop-namenode`

**解决：**
- 重新构建镜像：`docker-compose build --no-cache hadoop-namenode`
- 使用方案二（自动清理脚本）

### 问题：清理脚本无法执行

**检查：**
1. 确认容器正在运行：`docker ps`
2. 确认容器内有 Python 3：`docker exec hadoop-namenode python3 --version`
3. 确认配置文件路径正确：`docker exec hadoop-namenode ls -la /etc/hadoop/`

**解决：**
- 使用文本清理方法（脚本会自动回退）
- 手动编辑配置文件

### 问题：配置清理后服务无法启动

**检查：**
1. 查看服务日志：`docker logs hadoop-namenode`
2. 检查配置文件格式：`docker exec hadoop-namenode cat /etc/hadoop/core-site.xml | head -20`

**解决：**
- 从备份恢复配置文件
- 重新运行清理脚本
- 检查配置文件是否有必需的属性

## 注意事项

1. **配置文件挂载**：配置文件通过 volume 挂载，修改本地文件后需要重启容器才能生效
2. **备份配置**：在清理前建议备份配置文件
3. **定期检查**：定期运行清理脚本检查是否有新的重复配置
4. **官方镜像限制**：官方镜像（resourcemanager, nodemanager）无法修改 entrypoint，需要使用清理脚本

## 后续改进建议

1. **监控脚本**：创建定期监控脚本，自动检测并清理重复配置
2. **配置验证**：添加配置验证步骤，确保清理后的配置有效
3. **自动化集成**：将清理脚本集成到 CI/CD 流程中
4. **文档更新**：保持文档与代码同步更新

