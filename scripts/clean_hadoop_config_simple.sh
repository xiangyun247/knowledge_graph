#!/bin/bash
# 简单的 Hadoop 配置清理脚本
# 移除单行格式的重复配置项

CONTAINERS=("hadoop-namenode" "hadoop-datanode" "hadoop-resourcemanager" "hadoop-nodemanager")
CONFIG_FILES=("/etc/hadoop/core-site.xml" "/etc/hadoop/hdfs-site.xml" "/etc/hadoop/yarn-site.xml" "/etc/hadoop/mapred-site.xml")

for container in "${CONTAINERS[@]}"; do
    echo "Cleaning $container..."
    
    for config_file in "${CONFIG_FILES[@]}"; do
        # 使用 sed 移除所有单行格式的重复配置
        # 保留第一个出现的配置，删除后续重复的
        docker exec "$container" bash -c "
            # 创建临时文件
            temp_file=\$(mktemp)
            
            # 读取配置文件，移除重复的单行格式配置
            seen_props=()
            while IFS= read -r line; do
                if [[ \$line =~ ^\<property\>\<name\>([^\<]+)\</name\>\<value\>([^\<]+)\</value\>\</property\>$ ]]; then
                    prop_name=\${BASH_REMATCH[1]}
                    # 检查是否已存在
                    found=0
                    for seen in \"\${seen_props[@]}\"; do
                        if [ \"\$seen\" = \"\$prop_name\" ]; then
                            found=1
                            break
                        fi
                    done
                    if [ \$found -eq 0 ]; then
                        echo \"\$line\" >> \"\$temp_file\"
                        seen_props+=(\"\$prop_name\")
                    fi
                else
                    echo \"\$line\" >> \"\$temp_file\"
                fi
            done < \"$config_file\"
            
            # 替换原文件
            mv \"\$temp_file\" \"$config_file\"
        " 2>/dev/null || echo "Failed to clean $config_file in $container"
    done
    
    echo "Cleaned $container"
done

echo "All containers cleaned"

