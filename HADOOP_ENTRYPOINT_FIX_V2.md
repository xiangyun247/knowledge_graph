# Hadoop Entrypoint 修复 V2 - 防止重复配置追加

## 问题描述

即使清理脚本执行了，原始 entrypoint 在清理之后仍然会追加配置，导致重复配置问题依然存在。

## 根本原因

原始 entrypoint 的 `addProperty` 函数会在每次启动时无条件地向配置文件追加配置，即使配置已经存在。

## 解决方案

修改 entrypoint 脚本，创建一个修改后的 entrypoint 副本，其中 `addProperty` 函数会先检查配置是否已存在，如果存在则跳过添加。

### 工作流程

1. **清理现有重复配置**：在启动前清理配置文件中的重复项
2. **创建修改后的 entrypoint**：读取原始 entrypoint，替换 `addProperty` 函数
3. **执行修改后的 entrypoint**：使用修改后的 entrypoint 启动服务

### 修改后的 addProperty 函数

```bash
function addProperty() {
  local path=$1
  local name=$2
  local value=$3

  # 检查配置是否已存在
  local escaped_name=$(echo "$name" | sed 's/[[\.*^$()+?{|]/\\&/g')
  if grep -q "<name>$escaped_name</name>" "$path" 2>/dev/null; then
    echo "  - Skipping duplicate property: $name (already exists)"
    return 0
  fi

  # 如果不存在，则添加配置
  local entry="<property><name>$name</name><value>${value}</value></property>"
  local escapedEntry=$(echo $entry | sed 's/\//\\\//g')
  sed -i "/<\/configuration>/ s/.*/${escapedEntry}\n&/" $path
}
```

## 测试步骤

1. **重新构建镜像**：
   ```bash
   docker-compose build hadoop-namenode hadoop-datanode
   ```

2. **启动容器**：
   ```bash
   docker-compose up -d hadoop-namenode hadoop-datanode
   ```

3. **检查日志**：
   ```bash
   docker logs hadoop-namenode | grep -E "Cleaning|Skipping|duplicate"
   ```

4. **验证配置**：
   ```bash
   docker exec hadoop-namenode cat /etc/hadoop/core-site.xml
   # 应该只看到一个 fs.defaultFS 配置
   ```

## 预期结果

- 日志中应该看到 "Skipping duplicate property" 消息
- 配置文件中每个属性只出现一次
- 容器正常启动并保持运行

## 注意事项

1. 修改后的 entrypoint 存储在 `/tmp/modified-entrypoint.sh`
2. 每次容器启动都会重新创建修改后的 entrypoint
3. 如果原始 entrypoint 格式改变，可能需要调整替换逻辑

