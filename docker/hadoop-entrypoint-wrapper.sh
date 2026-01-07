#!/bin/bash
# Hadoop Entrypoint 包装脚本（简化版）
# 在 entrypoint 执行后清理重复配置

set -e

# 等待 entrypoint 脚本执行完成
# 这个脚本应该在 entrypoint 之后作为清理脚本运行

CONFIG_DIR="/etc/hadoop"
CONFIG_FILES=("core-site.xml" "hdfs-site.xml" "yarn-site.xml" "mapred-site.xml")

clean_config_file() {
    local config_file="$1"
    local full_path="${CONFIG_DIR}/${config_file}"
    
    if [ ! -f "$full_path" ]; then
        return 0
    fi
    
    python3 << 'PYTHON_SCRIPT'
import xml.etree.ElementTree as ET
import sys
import os

config_file = os.environ.get('CLEAN_CONFIG_FILE')
if not config_file:
    sys.exit(1)

try:
    tree = ET.parse(config_file)
    root = tree.getroot()
    
    seen_props = {}
    properties_to_keep = []
    
    for prop in root.findall('property'):
        name_elem = prop.find('name')
        if name_elem is not None:
            prop_name = name_elem.text
            if prop_name not in seen_props:
                seen_props[prop_name] = True
                properties_to_keep.append(prop)
    
    new_root = ET.Element('configuration')
    for prop in properties_to_keep:
        new_root.append(prop)
    
    tree = ET.ElementTree(new_root)
    tree.write(config_file, encoding='utf-8', xml_declaration=True)
    
    sys.exit(0)
except Exception:
    # 文本清理方法
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    seen_props = set()
    new_lines = []
    
    for line in lines:
        if '<property><name>' in line and '</property>' in line:
            import re
            match = re.search(r'<name>([^<]+)</name>', line)
            if match:
                prop_name = match.group(1)
                if prop_name not in seen_props:
                    seen_props.add(prop_name)
                    new_lines.append(line)
        else:
            new_lines.append(line)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    sys.exit(0)
PYTHON_SCRIPT
}

# 清理所有配置文件
for config_file in "${CONFIG_FILES[@]}"; do
    full_path="${CONFIG_DIR}/${config_file}"
    if [ -f "$full_path" ]; then
        export CLEAN_CONFIG_FILE="$full_path"
        clean_config_file "$config_file" || true
        unset CLEAN_CONFIG_FILE
    fi
done

