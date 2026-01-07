# Hadoop 配置重复问题快速修复指南

## 问题
Hadoop 容器的 entrypoint 脚本在每次启动时会追加配置，导致重复配置。

## 解决方案

### 方案一：自定义 Entrypoint（已实现，推荐）

**适用于：** hadoop-namenode, hadoop-datanode（自定义镜像）

**操作步骤：**
```bash
# 1. 重新构建镜像（使用新的 entrypoint）
docker-compose build hadoop-namenode hadoop-datanode

# 2. 启动容器
docker-compose up -d hadoop-namenode hadoop-datanode
```

**说明：** 自定义 entrypoint 会在启动前自动清理重复配置，无需手动操作。

### 方案二：自动清理脚本（备选方案）

**适用于：** 所有容器，特别是 hadoop-resourcemanager, hadoop-nodemanager（官方镜像）

**操作步骤：**
```bash
# 1. 运行自动清理脚本
python scripts/auto_clean_hadoop_configs.py

# 2. 重启容器以应用清理后的配置
docker-compose restart hadoop-resourcemanager hadoop-nodemanager
```

## 验证

检查配置文件是否正确：
```bash
# 检查是否有重复配置
docker exec hadoop-namenode cat /etc/hadoop/core-site.xml | grep -c "fs.defaultFS"
# 应该只返回 1

# 查看配置文件
docker exec hadoop-namenode cat /etc/hadoop/core-site.xml
```

## 文件说明

- `docker/hadoop-entrypoint.sh` - 自定义 entrypoint 脚本
- `scripts/auto_clean_hadoop_configs.py` - 自动清理脚本
- `HADOOP_CONFIG_CLEANUP_SOLUTION.md` - 详细文档

## 注意事项

1. 首次部署需要重新构建自定义镜像
2. 官方镜像容器（resourcemanager, nodemanager）需要手动运行清理脚本
3. 配置文件通过 volume 挂载，修改后需要重启容器

