#!/bin/bash
# 自定义 Hadoop Entrypoint 脚本
# 在调用原始 entrypoint 之前清理重复配置，避免 entrypoint 脚本重复追加配置

# 不使用 set -e，允许清理失败时继续执行原始 entrypoint
# set -e

# 配置文件路径
CONFIG_DIR="/etc/hadoop"
CONFIG_FILES=("core-site.xml" "hdfs-site.xml" "yarn-site.xml" "mapred-site.xml")

# 清理配置文件的函数
clean_config_file() {
    local config_file="$1"
    local full_path="${CONFIG_DIR}/${config_file}"
    
    if [ ! -f "$full_path" ]; then
        return 0
    fi
    
    # 检查文件是否有内容（至少要有 <configuration> 标签和一些内容）
    if ! grep -q "<configuration>" "$full_path" 2>/dev/null; then
        echo "  - Skipping $config_file (not a valid XML configuration file)"
        return 0
    fi
    
    # 检查文件是否有 property 标签
    if ! grep -q "<property>" "$full_path" 2>/dev/null; then
        echo "  - Skipping $config_file (no properties found)"
        return 0
    fi
    
    # 使用 Python 清理重复配置
    export CLEAN_CONFIG_FILE="$full_path"
    python3 << 'PYTHON_SCRIPT'
import xml.etree.ElementTree as ET
import sys
import os

config_file = os.environ.get('CLEAN_CONFIG_FILE')
if not config_file:
    sys.exit(1)

try:
    # 先读取原始内容以检查是否有样式表和注释
    with open(config_file, 'r', encoding='utf-8', errors='replace') as f:
        original_content = f.read()
    has_stylesheet = 'xml-stylesheet' in original_content
    
    # 解析配置文件
    try:
        tree = ET.parse(config_file)
        root = tree.getroot()
    except ET.ParseError:
        # 如果解析失败，使用文本清理方法
        raise Exception("XML parse error")
    
    # 收集所有 property，保留第一个出现的
    seen_props = {}
    properties_to_keep = []
    
    for prop in root.findall('property'):
        name_elem = prop.find('name')
        if name_elem is not None and name_elem.text:
            prop_name = name_elem.text.strip()
            if prop_name and prop_name not in seen_props:
                seen_props[prop_name] = True
                properties_to_keep.append(prop)
    
    # 如果没有属性，不要清空文件，直接返回（保持原文件不变）
    if not properties_to_keep:
        # 不修改文件，直接退出
        sys.exit(0)
    
    # 重建 XML
    new_root = ET.Element('configuration')
    for prop in properties_to_keep:
        new_root.append(prop)
    
    # 格式化 XML（添加缩进）
    def indent(elem, level=0):
        i = "\n" + "    " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                indent(child, level+1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    indent(new_root)
    
    # 生成 XML 内容
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if has_stylesheet:
        xml_content += '<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>\n'
    xml_content += ET.tostring(new_root, encoding='unicode')
    
    # 写回文件
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    sys.exit(0)
except Exception as e:
    # 如果 XML 解析失败，尝试简单的文本清理
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    seen_props = set()
    new_lines = []
    in_property = False
    current_prop = None
    prop_lines = []
    
    for line in lines:
        # 检查是否是单行格式的 property
        if '<property><name>' in line and '</property>' in line:
            import re
            match = re.search(r'<name>([^<]+)</name>', line)
            if match:
                prop_name = match.group(1)
                if prop_name not in seen_props:
                    seen_props.add(prop_name)
                    new_lines.append(line)
        elif '<property>' in line and '</property>' not in line:
            # 多行格式开始
            in_property = True
            prop_lines = [line]
        elif in_property:
            prop_lines.append(line)
            if '<name>' in line:
                import re
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
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    sys.exit(0)
PYTHON_SCRIPT
    unset CLEAN_CONFIG_FILE
}

# 在容器启动时清理所有配置文件
# 注意：只在文件有有效内容时才清理，避免清空文件
echo "Cleaning Hadoop configuration files to remove duplicates..."
for config_file in "${CONFIG_FILES[@]}"; do
    if [ -f "${CONFIG_DIR}/${config_file}" ]; then
        # 检查文件是否有有效内容
        if [ -s "${CONFIG_DIR}/${config_file}" ] && grep -q "<property>" "${CONFIG_DIR}/${config_file}" 2>/dev/null; then
            echo "  Cleaning ${config_file}..."
            # 即使清理失败也继续执行
            clean_config_file "$config_file" 2>&1 || echo "  Warning: Failed to clean ${config_file}, continuing..."
        else
            echo "  Skipping ${config_file} (empty or no properties)"
        fi
    fi
done
echo "Configuration cleanup completed."

# 调用原始 entrypoint 脚本
# 查找原始 entrypoint 脚本的位置（优先使用备份的）
ORIGINAL_ENTRYPOINT="/original-entrypoint.sh"
if [ ! -f "$ORIGINAL_ENTRYPOINT" ]; then
    ORIGINAL_ENTRYPOINT="/entrypoint.sh"
fi
if [ ! -f "$ORIGINAL_ENTRYPOINT" ]; then
    ORIGINAL_ENTRYPOINT="/usr/local/bin/entrypoint.sh"
fi

if [ -f "$ORIGINAL_ENTRYPOINT" ]; then
    echo "Executing original entrypoint: $ORIGINAL_ENTRYPOINT"
    
    # 创建一个修改后的 entrypoint，它会检查配置是否已存在再添加
    MODIFIED_ENTRYPOINT="/tmp/modified-entrypoint.sh"
    
    # 使用更简单可靠的方法：直接使用 Python 处理文件（二进制模式）
    python3 << 'PYTHON_REPLACE'
import sys
import re

# 读取原始文件（二进制模式）
try:
    with open('$ORIGINAL_ENTRYPOINT', 'rb') as f:
        content_bytes = f.read()
    
    # 尝试多种编码
    content = None
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            content = content_bytes.decode(encoding)
            break
        except:
            continue
    
    if content is None:
        content = content_bytes.decode('utf-8', errors='replace')
    
    # 新的 addProperty 函数
    new_func = '''function addProperty() {
  local path=$1
  local name=$2
  local value=$3

  local escaped_name=$(echo "$name" | sed 's/[[\.*^$()+?{|]/\\&/g')
  if grep -q "<name>$escaped_name</name>" "$path" 2>/dev/null; then
    echo "  - Skipping duplicate property: $name (already exists)"
    return 0
  fi

  local entry="<property><name>$name</name><value>${value}</value></property>"
  local escapedEntry=$(echo $entry | sed 's/\//\\\//g')
  sed -i "/<\/configuration>/ s/.*/${escapedEntry}\n&/" $path
}'''
    
    # 替换函数
    pattern = r'function addProperty\(\)\s*\{[^}]*\}'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_func, content, flags=re.DOTALL)
    
    # 写入文件（二进制模式，UTF-8编码）
    with open('$MODIFIED_ENTRYPOINT', 'wb') as f:
        f.write(content.encode('utf-8', errors='replace'))
    
    sys.exit(0)
except Exception as e:
    # 如果失败，直接复制原始文件
    import shutil
    shutil.copy('$ORIGINAL_ENTRYPOINT', '$MODIFIED_ENTRYPOINT')
    sys.exit(1)
PYTHON_REPLACE
    
    # 检查文件是否创建成功
    if [ ! -f "$MODIFIED_ENTRYPOINT" ] || [ ! -s "$MODIFIED_ENTRYPOINT" ]; then
        echo "Warning: Failed to create modified entrypoint, using original"
        cp "$ORIGINAL_ENTRYPOINT" "$MODIFIED_ENTRYPOINT"
    fi
    
    chmod +x "$MODIFIED_ENTRYPOINT"
    echo "Created modified entrypoint with duplicate check: $MODIFIED_ENTRYPOINT"
    
    # 如果没有传递参数，使用默认的 /run.sh（基础镜像的默认 CMD）
    if [ $# -eq 0 ]; then
        echo "No command provided, using default: /run.sh"
        exec "$MODIFIED_ENTRYPOINT" /run.sh
    else
        # 使用 exec 替换当前进程，确保修改后的 entrypoint 成为主进程
        exec "$MODIFIED_ENTRYPOINT" "$@"
    fi
else
    echo "Error: Original entrypoint not found at $ORIGINAL_ENTRYPOINT"
    echo "Available entrypoints:"
    ls -la /entrypoint.sh /usr/local/bin/entrypoint.sh 2>/dev/null || true
    # 如果没有参数，尝试运行默认命令
    if [ $# -eq 0 ]; then
        echo "No command provided, trying default: /run.sh"
        exec /run.sh
    else
        echo "Executing command directly: $@"
        exec "$@"
    fi
fi

