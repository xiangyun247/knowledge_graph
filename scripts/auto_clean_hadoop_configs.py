#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动清理 Hadoop 配置文件中的重复配置项
在容器启动后自动执行，确保配置文件中没有重复项

使用方法：
1. 手动运行：python scripts/auto_clean_hadoop_configs.py
2. 在 docker-compose 中使用：作为容器启动后的清理脚本
"""

import subprocess
import sys
import re
import time


def clean_xml_config_in_container(container_name, config_path):
    """
    清理容器内的 XML 配置文件，移除重复的 <property> 块（按 <name> 去重）。

    设计目标：
    - **不再依赖 XML 解析库**，避免因注释、格式差异导致 ParseError
    - **尽量保持原始结构**（注释、空行、缩进等），只删除重复的 property 块
    """
    print(f"Cleaning {config_path} in {container_name}...")

    # 读取容器内的配置文件（原样文本）
    read_cmd = ["docker", "exec", container_name, "cat", config_path]
    result = subprocess.run(read_cmd, capture_output=True, text=True, encoding="utf-8")

    if result.returncode != 0:
        print(f"  ✗ Failed to read {config_path}: {result.stderr}")
        return False

    content = result.stdout

    # 简单检查：必须包含 <configuration> 才认为是合法配置文件
    if "<configuration" not in content:
        print(f"  ⚠ {config_path} does not look like a Hadoop XML config, skip")
        return True

    # 使用正则匹配 <property>...</property> 块（多行或单行都支持）
    prop_pattern = re.compile(r"<property>.*?</property>", re.DOTALL)

    seen_props = set()
    removed_count = 0
    new_content_parts = []
    last_index = 0

    for match in prop_pattern.finditer(content):
        start, end = match.start(), match.end()
        block = match.group(0)

        # 先把 property 块之前的文本原样保留
        new_content_parts.append(content[last_index:start])

        name_match = re.search(r"<name>([^<]+)</name>", block)
        prop_name = name_match.group(1).strip() if name_match else None

        if prop_name and prop_name in seen_props:
            removed_count += 1
            print(f"  - Removed duplicate: {prop_name}")
            # 跳过该块（不加入 new_content_parts）
        else:
            if prop_name:
                seen_props.add(prop_name)
            new_content_parts.append(block)

        last_index = end

    # 追加最后一个 property 之后的所有内容
    new_content_parts.append(content[last_index:])
    new_content = "".join(new_content_parts)

    if removed_count == 0:
        print(f"  ✓ No duplicates found in {config_path}")
        return True

    # 写回容器
    # 先处理内容，避免在 f-string 中使用反斜杠
    escaped_content = new_content.replace("'", "\\'").replace("\\", "\\\\")
    write_script = f"""
content = '''{escaped_content}'''
with open('{config_path}', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK')
"""

    write_cmd = ["docker", "exec", "-i", container_name, "python3", "-c", write_script]
    write_result = subprocess.run(write_cmd, capture_output=True, text=True, encoding="utf-8")

    if write_result.returncode == 0:
        print(
            f"  ✓ Cleaned {config_path} "
            f"(removed {removed_count} duplicates, kept {len(seen_props)} unique properties)"
        )
        return True
    else:
        print(f"  ✗ Failed to write {config_path}: {write_result.stderr}")
        return False

def wait_for_container(container_name, max_wait=60):
    """等待容器启动"""
    print(f"Waiting for {container_name} to be ready...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        if container_name in result.stdout:
            # 检查容器是否健康（如果可以执行命令）
            test_cmd = ["docker", "exec", container_name, "echo", "ready"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True)
            if test_result.returncode == 0:
                print(f"  ✓ {container_name} is ready")
                return True
        
        time.sleep(2)
    
    print(f"  ✗ {container_name} did not become ready within {max_wait} seconds")
    return False

def clean_container_configs(container_name, wait=True):
    """清理指定容器的所有配置文件"""
    if wait:
        if not wait_for_container(container_name):
            return False
    
    config_files = [
        "/etc/hadoop/core-site.xml",
        "/etc/hadoop/hdfs-site.xml",
        "/etc/hadoop/yarn-site.xml",
        "/etc/hadoop/mapred-site.xml"
    ]
    
    success_count = 0
    total_count = 0
    
    print(f"\n=== Cleaning {container_name} ===")
    for config_file in config_files:
        total_count += 1
        if clean_xml_config_in_container(container_name, config_file):
            success_count += 1
    
    print(f"Cleaned {success_count}/{total_count} configuration files in {container_name}")
    return success_count == total_count

def main():
    """主函数"""
    containers = [
        "hadoop-namenode",
        "hadoop-datanode",
        "hadoop-resourcemanager",
        "hadoop-nodemanager"
    ]
    
    success_count = 0
    total_count = 0
    
    for container in containers:
        # 检查容器是否运行
        check_cmd = ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if container not in check_result.stdout:
            print(f"Container {container} is not running, skipping...")
            continue
        
        total_count += 1
        if clean_container_configs(container, wait=False):
            success_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Cleaned {success_count}/{total_count} containers")
    
    if success_count < total_count:
        print("\n⚠ Some containers failed to clean.")
        return 1
    
    if success_count > 0:
        print("\n✓ All configuration files cleaned successfully!")
        print("\nNote: You may need to restart containers for changes to take full effect.")
        print("Run: docker-compose restart hadoop-namenode hadoop-datanode hadoop-nodemanager hadoop-resourcemanager")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

