#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速修复容器内的Hadoop配置文件
"""

import subprocess
import xml.etree.ElementTree as ET

def fix_core_site(container_name):
    """修复core-site.xml，只保留正确的fs.defaultFS配置"""
    print(f"Fixing core-site.xml in {container_name}...")
    
    # 读取容器内的文件
    read_cmd = ["docker", "exec", container_name, "cat", "/etc/hadoop/core-site.xml"]
    result = subprocess.run(read_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ✗ Failed to read: {result.stderr}")
        return False
    
    try:
        # 解析XML
        root = ET.fromstring(result.stdout)
        
        # 创建新的配置，只保留正确的fs.defaultFS
        new_root = ET.Element('configuration')
        
        # 添加正确的fs.defaultFS
        prop1 = ET.SubElement(new_root, 'property')
        name1 = ET.SubElement(prop1, 'name')
        name1.text = 'fs.defaultFS'
        value1 = ET.SubElement(prop1, 'value')
        value1.text = 'hdfs://hadoop-namenode:8020'
        
        # 添加proxyuser配置
        prop2 = ET.SubElement(new_root, 'property')
        name2 = ET.SubElement(prop2, 'name')
        name2.text = 'hadoop.proxyuser.root.hosts'
        value2 = ET.SubElement(prop2, 'value')
        value2.text = '*'
        
        prop3 = ET.SubElement(new_root, 'property')
        name3 = ET.SubElement(prop3, 'name')
        name3.text = 'hadoop.proxyuser.root.groups'
        value3 = ET.SubElement(prop3, 'value')
        value3.text = '*'
        
        # 格式化
        ET.indent(new_root, space='    ')
        new_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        new_content += '<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>\n'
        new_content += ET.tostring(new_root, encoding='unicode')
        
        # 写回容器
        write_script = f"""
import sys
content = '''{new_content.replace("'", "\\'")}'''
with open('/etc/hadoop/core-site.xml', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK')
"""
        
        write_cmd = ["docker", "exec", "-i", container_name, "python3", "-c", write_script]
        write_result = subprocess.run(write_cmd, capture_output=True, text=True)
        
        if write_result.returncode == 0:
            print(f"  ✓ Fixed core-site.xml")
            return True
        else:
            print(f"  ✗ Failed to write: {write_result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    containers = ["hadoop-namenode", "hadoop-datanode", "hadoop-nodemanager"]
    
    for container in containers:
        check_cmd = ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if container not in check_result.stdout:
            print(f"Container {container} is not running, skipping...")
            continue
        
        print(f"\n=== Fixing {container} ===")
        fix_core_site(container)
    
    print("\n✓ Done! Restarting containers...")
    subprocess.run(["docker-compose", "restart", "hadoop-namenode", "hadoop-datanode", "hadoop-nodemanager"], 
                  capture_output=True)

if __name__ == "__main__":
    main()

