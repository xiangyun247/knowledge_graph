# PowerShell script to clean Hadoop config files in containers
# This should be run after containers start

$containers = @("hadoop-namenode", "hadoop-datanode", "hadoop-nodemanager")

foreach ($container in $containers) {
    Write-Host "Cleaning $container..."
    
    # Clean core-site.xml - keep only the correct fs.defaultFS
    $cleanScript = @"
import xml.etree.ElementTree as ET
import sys

try:
    # Read file
    tree = ET.parse('/etc/hadoop/core-site.xml')
    root = tree.getroot()
    
    # Create new root with only correct properties
    new_root = ET.Element('configuration')
    
    # Add correct fs.defaultFS
    prop1 = ET.SubElement(new_root, 'property')
    name1 = ET.SubElement(prop1, 'name')
    name1.text = 'fs.defaultFS'
    value1 = ET.SubElement(prop1, 'value')
    value1.text = 'hdfs://hadoop-namenode:8020'
    
    # Add proxyuser configs
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
    
    # Format and write
    ET.indent(new_root, space='    ')
    content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    content += '<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>\n'
    content += ET.tostring(new_root, encoding='unicode')
    
    with open('/etc/hadoop/core-site.xml', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('OK')
    sys.exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"@
    
    $result = docker exec $container python3 -c $cleanScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Cleaned core-site.xml"
    } else {
        Write-Host "  ✗ Failed: $result"
    }
}

Write-Host "`nRestarting containers to apply changes..."
docker-compose restart hadoop-namenode hadoop-datanode hadoop-nodemanager

