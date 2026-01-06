# Hadoop 配置文件目录

## 📁 说明

此目录用于存放 Hadoop 的自定义配置文件。

## 🔧 配置文件

Hadoop 的配置文件会挂载到此目录，包括：
- `core-site.xml` - 核心配置
- `hdfs-site.xml` - HDFS 配置
- `yarn-site.xml` - YARN 配置
- `mapred-site.xml` - MapReduce 配置

## 📝 注意事项

- 配置文件会在 Docker Compose 启动时自动挂载
- 修改配置后需要重启 Hadoop 服务
- 建议使用 Docker Compose 管理配置


