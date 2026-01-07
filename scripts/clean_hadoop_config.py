#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 Hadoop 配置文件中的重复配置项
在容器启动后运行此脚本，移除 entrypoint 脚本添加的重复配置
"""

import re
import sys
import subprocess

def clean_config_file(container_name, config_file):
    """清理配置文件中的重复配置"""
    print(f"Cleaning {config_file} in {container_name}...")
    
    script = f"""
import re

# 读取配置文件
with open('{config_file}', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除所有单行格式的重复配置
seen_props = {{}}
lines = content.split('\\n')
new_lines = []
in_property = False
current_prop = None
prop_lines = []

for line in lines:
    # 检查是否是单行格式的 property
    match = re.match(r'<property><name>([^<]+)</name><value>([^<]+)</value></property>', line.strip())
    if match:
        prop_name = match.group(1)
        if prop_name in seen_props:
            continue  # 跳过重复的
        seen_props.add(prop_name)
        new_lines.append(line)
    elif '<property>' in line and '<name>' not in line:
        # 多行格式的 property，需要特殊处理
        in_property = True
        prop_lines = [line]
    elif in_property:
        prop_lines.append(line)
        if '<name>' in line:
            match = re.search(r'<name>([^<]+)</name>', line)
            if match:
                current_prop = match.group(1)
        if '</property>' in line:
            if current_prop and current_prop not in seen_props:
                seen_props.add(current_prop)
                new_lines.extend(prop_lines)
            in_property = False
            current_prop = None
            prop_lines = []
    else:
        new_lines.append(line)

# 写回文件
with open('{config_file}', 'w', encoding='utf-8') as f:
    f.write('\\n'.join(new_lines))

print('Cleaned successfully')
"""
    
    result = subprocess.run(
        ["docker", "exec", container_name, "python3", "-c", script],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"✓ {config_file} cleaned")
    else:
        print(f"✗ Failed to clean {config_file}: {result.stderr}")

def main():
    """主函数"""
    containers = [
        "hadoop-namenode",
        "hadoop-datanode",
        "hadoop-resourcemanager",
        "hadoop-nodemanager"
    ]
    
    config_files = [
        "/etc/hadoop/core-site.xml",
        "/etc/hadoop/hdfs-site.xml",
        "/etc/hadoop/yarn-site.xml",
        "/etc/hadoop/mapred-site.xml"
    ]
    
    for container in containers:
        # 检查容器是否运行
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        if container not in result.stdout:
            print(f"Container {container} is not running, skipping...")
            continue
        
        for config_file in config_files:
            clean_config_file(container, config_file)
        
        # 重启容器以应用清理后的配置
        print(f"Restarting {container}...")
        subprocess.run(["docker", "restart", container], capture_output=True)

if __name__ == "__main__":
    main()

