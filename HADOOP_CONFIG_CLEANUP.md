# Hadoop 配置文件清理记录

## 问题描述

Hadoop 配置文件（`core-site.xml`, `hdfs-site.xml`, `yarn-site.xml`, `mapred-site.xml`）中出现了大量重复的配置项。

**原因分析：**
- 基础镜像的 entrypoint 脚本会根据环境变量自动添加配置
- 每次容器启动时，entrypoint 脚本会追加配置到现有配置文件
- 如果环境变量设置了多次，或者脚本运行多次，就会产生重复配置

## 清理结果

### 清理前
- `core-site.xml`: 8 个重复的 `fs.defaultFS` 配置
- `hdfs-site.xml`: 57 行，大量重复配置
- `yarn-site.xml`: 25 行，大量重复配置
- `mapred-site.xml`: 10 行，大量重复配置

### 清理后
- `core-site.xml`: 3 个属性（fs.defaultFS, hadoop.proxyuser.root.hosts, hadoop.proxyuser.root.groups）
- `hdfs-site.xml`: 9 个属性（NameNode 和 DataNode 配置）
- `mapred-site.xml`: 1 个属性（mapreduce.framework.name）
- `yarn-site.xml`: 3 个属性（ResourceManager, NodeManager, Timeline Service 绑定地址）

## 配置文件内容

### core-site.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <property>
        <name>fs.defaultFS</name>
        <value>hdfs://hadoop-namenode:8020</value>
    </property>
    <property>
        <name>hadoop.proxyuser.root.hosts</name>
        <value>*</value>
    </property>
    <property>
        <name>hadoop.proxyuser.root.groups</name>
        <value>*</value>
    </property>
</configuration>
```

### hdfs-site.xml
- dfs.namenode.name.dir
- dfs.namenode.rpc-bind-host
- dfs.namenode.servicerpc-bind-host
- dfs.namenode.http-bind-host
- dfs.namenode.https-bind-host
- dfs.datanode.data.dir
- dfs.client.use.datanode.hostname
- dfs.datanode.use.datanode.hostname
- dfs.replication

### mapred-site.xml
- mapreduce.framework.name = yarn

### yarn-site.xml
- yarn.resourcemanager.bind-host
- yarn.nodemanager.bind-host
- yarn.timeline-service.bind-host

## 防止重复配置的方法

### 方法 1: 使用标准 XML 格式（已采用）
确保配置文件使用标准的多行格式，而不是单行格式：
```xml
<property>
    <name>property.name</name>
    <value>property.value</value>
</property>
```

### 方法 2: 定期检查
在容器启动后检查配置文件，确保没有重复：
```bash
docker exec hadoop-namenode bash -c "grep -c '<property>' /etc/hadoop/core-site.xml"
```

### 方法 3: 使用清理脚本
如果发现重复配置，可以使用清理脚本：
```bash
python scripts/clean_hadoop_config.py
```

## 注意事项

- 配置文件通过 volume 挂载，修改本地文件后需要重启容器
- entrypoint 脚本可能会再次添加配置，需要定期检查
- 建议在每次容器启动后验证配置文件是否正确

## 清理时间

2026年1月7日
