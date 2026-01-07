#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理容器内 Hadoop 配置文件中的重复配置项
移除 entrypoint 脚本添加的单行格式重复配置
"""

import subprocess
import sys
import xml.etree.ElementTree as ET
from io import StringIO

def clean_xml_config(container_name, config_path):
    """清理 XML 配置文件，移除重复的 property"""
    print(f"Cleaning {config_path} in {container_name}...")
    
    # 读取容器内的配置文件
    read_cmd = ["docker", "exec", container_name, "cat", config_path]
    result = subprocess.run(read_cmd, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode != 0:
        print(f"  ✗ Failed to read {config_path}: {result.stderr}")
        return False
    
    content = result.stdout
    
    try:
        # 解析 XML
        root = ET.fromstring(content)
        
        # 收集所有 property，保留第一个出现的
        seen_props = {}
        properties_to_keep = []
        
        for prop in root.findall('property'):
            name_elem = prop.find('name')
            if name_elem is not None:
                prop_name = name_elem.text
                if prop_name not in seen_props:
                    seen_props[prop_name] = prop.find('value').text if prop.find('value') is not None else None
                    properties_to_keep.append(prop)
                else:
                    print(f"  - Removed duplicate: {prop_name}")
        
        # 重建 XML
        new_root = ET.Element('configuration')
        for prop in properties_to_keep:
            new_root.append(prop)
        
        # 格式化输出
        ET.indent(new_root, space='    ')
        new_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        new_content += '<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>\n'
        new_content += ET.tostring(new_root, encoding='unicode')
        
        # 写回容器
        write_script = f"""
import sys
content = '''{new_content.replace("'", "\\'")}'''
with open('{config_path}', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK')
"""
        
        write_cmd = ["docker", "exec", "-i", container_name, "python3", "-c", write_script]
        write_result = subprocess.run(write_cmd, capture_output=True, text=True, encoding='utf-8')
        
        if write_result.returncode == 0:
            print(f"  ✓ Cleaned {config_path} ({len(properties_to_keep)} unique properties)")
            return True
        else:
            print(f"  ✗ Failed to write {config_path}: {write_result.stderr}")
            return False
            
    except ET.ParseError as e:
        print(f"  ✗ XML parse error: {e}")
        # 尝试简单的文本清理
        return clean_text_config(container_name, config_path, content)

def clean_text_config(container_name, config_path, content):
    """简单的文本清理方法（备用）"""
    lines = content.split('\n')
    seen_props = set()
    new_lines = []
    
    for line in lines:
        # 检查单行格式的 property
        if '<property><name>' in line and '</property>' in line:
            # 提取属性名
            import re
            match = re.search(r'<name>([^<]+)</name>', line)
            if match:
                prop_name = match.group(1)
                if prop_name in seen_props:
                    continue  # 跳过重复
                seen_props.add(prop_name)
        new_lines.append(line)
    
    new_content = '\n'.join(new_lines)
    
    # 写回容器
    write_script = f"""
content = '''{new_content.replace("'", "\\'")}'''
with open('{config_path}', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK')
"""
    
    write_cmd = ["docker", "exec", "-i", container_name, "python3", "-c", write_script]
    write_result = subprocess.run(write_cmd, capture_output=True, text=True, encoding='utf-8')
    
    if write_result.returncode == 0:
        print(f"  ✓ Cleaned {config_path} (text method)")
        return True
    else:
        print(f"  ✗ Failed: {write_result.stderr}")
        return False

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
    
    success_count = 0
    total_count = 0
    
    for container in containers:
        # 检查容器是否运行
        check_cmd = ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if container not in check_result.stdout:
            print(f"Container {container} is not running, skipping...")
            continue
        
        print(f"\n=== Cleaning {container} ===")
        for config_file in config_files:
            total_count += 1
            if clean_xml_config(container, config_file):
                success_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Cleaned {success_count}/{total_count} configuration files")
    
    if success_count < total_count:
        print("\n⚠ Some files failed to clean. You may need to restart containers manually.")
        return 1
    
    print("\n✓ All configuration files cleaned successfully!")
    print("\nNote: Containers need to be restarted for changes to take effect.")
    print("Run: docker-compose restart hadoop-namenode hadoop-datanode hadoop-nodemanager hadoop-resourcemanager")
    return 0

if __name__ == "__main__":
    sys.exit(main())

