# Hadoop 问题修复总结

## 修复日期
2026年1月7日

## 修复的问题

### 1. Hadoop 配置文件重复问题 ✅

**问题描述：**
- Hadoop 容器的 entrypoint 脚本会自动向配置文件追加配置，导致重复和错误的配置
- `hdfs-site.xml`、`mapred-site.xml`、`yarn-site.xml` 中都存在重复的配置项

**修复内容：**
- 清理了 `hadoop/config/hdfs-site.xml` 中的重复配置项（移除了40-52行的重复配置）
- 清理了 `hadoop/config/mapred-site.xml` 中的重复配置项（移除了8-10行的重复配置）
- 清理了 `hadoop/config/yarn-site.xml` 中的重复配置项（移除了16-27行的重复配置）

**配置文件状态：**
- `core-site.xml`: 3个属性（fs.defaultFS, hadoop.proxyuser.root.hosts, hadoop.proxyuser.root.groups）
- `hdfs-site.xml`: 9个属性（NameNode 和 DataNode 配置）
- `mapred-site.xml`: 1个属性（mapreduce.framework.name）
- `yarn-site.xml`: 3个属性（ResourceManager, NodeManager, Timeline Service 绑定地址）

### 2. MapReduce 脚本错误修复 ✅

**问题描述：**
- MapReduce 脚本错误，导致文件批量删除上传后无法正确提取PDF

**修复内容：**

#### mapper.py 改进：
1. **改进错误处理**：
   - 添加了更详细的错误日志
   - 改进了HDFS路径清理（移除换行符和空白）
   - 添加了文件存在性检查

2. **改进HDFS文件下载**：
   - 支持多种hadoop命令路径（HADOOP_HOME环境变量或系统PATH）
   - 改进了临时文件命名（使用MD5哈希避免冲突）
   - 添加了重试机制（如果HADOOP_HOME路径失败，回退到系统hadoop命令）

3. **改进PDF提取**：
   - 添加了页面级别的错误处理（单页失败不影响整个文件）
   - 改进了文本清理逻辑

4. **改进输入处理**：
   - 使用二进制模式读取stdin，避免编码问题
   - 添加了注释行跳过功能
   - 添加了处理统计（成功/失败计数）

#### reducer.py 改进：
1. **改进错误处理**：
   - 添加了更详细的日志记录
   - 改进了输入格式验证
   - 添加了处理统计

2. **改进输出处理**：
   - 改进了文本合并逻辑
   - 添加了错误标记处理（ERROR开头的文本仍然输出，但记录警告）

## 测试步骤

### 1. 重启Hadoop容器以应用配置更改

```bash
docker-compose restart hadoop-namenode hadoop-datanode hadoop-nodemanager hadoop-resourcemanager
```

或者如果需要完全重建：

```bash
docker-compose down
docker-compose up -d
```

### 2. 验证配置文件

运行清理脚本验证配置文件是否正确：

```bash
python scripts/clean_container_configs.py
```

### 3. 运行测试脚本

确保：
- 后端服务正在运行（`http://127.0.0.1:5001`）
- 测试PDF文件存在于指定路径（`C:\Users\23035\Desktop\pdf_test1.pdf` 和 `pdf_test2.pdf`）

然后运行：

```bash
python tests/test_batch_build.py
```

## 预期结果

1. **配置文件**：所有配置文件应该只包含唯一的配置项，没有重复
2. **批量上传**：PDF文件应该能够成功上传到HDFS
3. **PDF提取**：MapReduce任务应该能够成功提取PDF文本
4. **任务状态**：任务应该能够完成并返回SUCCESS状态

## 注意事项

1. **配置文件挂载**：配置文件通过volume挂载，修改本地文件后需要重启容器才能生效
2. **Entrypoint脚本**：基础镜像的entrypoint脚本可能会再次添加配置，如果发现重复配置，可以运行清理脚本
3. **Hadoop命令路径**：mapper.py现在支持多种hadoop命令路径，如果遇到问题，检查HADOOP_HOME环境变量
4. **临时文件清理**：mapper.py会自动清理临时文件，但如果任务异常终止，可能需要手动清理`/tmp`目录

## 后续建议

1. **监控配置**：定期检查配置文件，确保没有重复配置
2. **日志分析**：查看MapReduce任务的日志，确保PDF提取正常工作
3. **性能优化**：如果处理大量文件，考虑优化MapReduce任务的资源配置

