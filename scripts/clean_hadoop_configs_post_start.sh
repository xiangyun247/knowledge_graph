#!/bin/bash
# 容器启动后自动清理 Hadoop 配置脚本
# 这个脚本可以在容器启动后作为清理任务运行

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
    removed_count = 0
    
    for prop in root.findall('property'):
        name_elem = prop.find('name')
        if name_elem is not None:
            prop_name = name_elem.text
            if prop_name not in seen_props:
                seen_props[prop_name] = True
                properties_to_keep.append(prop)
            else:
                removed_count += 1
    
    if removed_count == 0:
        sys.exit(0)
    
    new_root = ET.Element('configuration')
    for prop in properties_to_keep:
        new_root.append(prop)
    
    tree = ET.ElementTree(new_root)
    tree.write(config_file, encoding='utf-8', xml_declaration=True)
    
    # 添加 XML 样式表声明
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'xml-stylesheet' not in content:
        content = content.replace(
            '<?xml version=\'1.0\' encoding=\'utf-8\'?>',
            '<?xml version="1.0" encoding="UTF-8"?>\n<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>'
        )
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
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
echo "Cleaning Hadoop configuration files..."
for config_file in "${CONFIG_FILES[@]}"; do
    full_path="${CONFIG_DIR}/${config_file}"
    if [ -f "$full_path" ]; then
        export CLEAN_CONFIG_FILE="$full_path"
        if clean_config_file "$config_file"; then
            echo "  ✓ Cleaned $config_file"
        else
            echo "  ✗ Failed to clean $config_file"
        fi
        unset CLEAN_CONFIG_FILE
    fi
done

echo "Configuration cleanup completed."

