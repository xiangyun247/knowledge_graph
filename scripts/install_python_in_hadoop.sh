#!/bin/bash
# 在运行中的 Hadoop 容器中安装 Python（临时方案）

echo "在 Hadoop 容器中安装 Python..."

# 配置使用 Debian 存档源
docker exec hadoop-namenode bash -c "cat > /etc/apt/sources.list << 'EOF'
deb http://archive.debian.org/debian stretch main
deb http://archive.debian.org/debian-security stretch/updates main
EOF"

docker exec hadoop-namenode bash -c "echo 'Acquire::Check-Valid-Until false;' > /etc/apt/apt.conf.d/99no-check-valid-until"

# 安装 Python 3
docker exec hadoop-namenode bash -c "apt-get update && apt-get install -y python3 python3-pip"

# 安装 Python 依赖
docker exec hadoop-namenode bash -c "pip3 install pdfplumber"

# 创建 Python 软链接
docker exec hadoop-namenode bash -c "ln -sf /usr/bin/python3 /usr/bin/python || true"

echo "Python 安装完成！"
docker exec hadoop-namenode python3 --version
docker exec hadoop-namenode pip3 list | grep pdfplumber

