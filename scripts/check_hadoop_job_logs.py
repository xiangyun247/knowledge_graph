#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Hadoop 任务日志

用于诊断 mapper 脚本执行失败的原因
"""

import subprocess
import sys
import json
from datetime import datetime, timedelta

CONTAINER_NAME = "hadoop-namenode"


def list_recent_applications():
    """列出最近的应用"""
    print("=" * 60)
    print("列出最近的 Hadoop 应用")
    print("=" * 60)
    
    cmd = ["docker", "exec", CONTAINER_NAME, "yarn", "application", "-list"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
    
    if result.returncode == 0:
        print(result.stdout)
        return result.stdout
    else:
        print(f"错误: {result.stderr}")
        return None


def get_application_logs(app_id):
    """获取应用日志"""
    print(f"\n{'='*60}")
    print(f"获取应用日志: {app_id}")
    print(f"{'='*60}")
    
    cmd = ["docker", "exec", CONTAINER_NAME, "yarn", "logs", "-applicationId", app_id]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='ignore')
    
    if result.returncode == 0:
        print(result.stdout)
        return result.stdout
    else:
        print(f"错误: {result.stderr}")
        return None


def find_container_logs():
    """查找容器日志目录"""
    print(f"\n{'='*60}")
    print("查找容器日志")
    print(f"{'='*60}")
    
    # 查找最近的日志目录
    cmd = ["docker", "exec", CONTAINER_NAME, "find", "/opt/hadoop-3.2.1/logs/userlogs", 
           "-type", "d", "-maxdepth", "1", "-mtime", "-1"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
    
    if result.returncode == 0:
        dirs = result.stdout.strip().split('\n')
        dirs = [d for d in dirs if d.strip()]
        print(f"找到 {len(dirs)} 个日志目录")
        
        for log_dir in dirs[:5]:  # 只显示前5个
            print(f"\n检查目录: {log_dir}")
            # 列出目录内容
            cmd2 = ["docker", "exec", CONTAINER_NAME, "ls", "-la", log_dir]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore')
            if result2.returncode == 0:
                print(result2.stdout)
            
            # 查找 stderr 文件
            cmd3 = ["docker", "exec", CONTAINER_NAME, "find", log_dir, "-name", "stderr"]
            result3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore')
            if result3.returncode == 0 and result3.stdout.strip():
                stderr_file = result3.stdout.strip().split('\n')[0]
                print(f"\n读取 stderr: {stderr_file}")
                cmd4 = ["docker", "exec", CONTAINER_NAME, "cat", stderr_file]
                result4 = subprocess.run(cmd4, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore')
                if result4.returncode == 0:
                    print(result4.stdout[-2000:])  # 最后2000字符
    else:
        print(f"错误: {result.stderr}")


def check_hdfs_error_logs():
    """检查 HDFS 错误日志"""
    print(f"\n{'='*60}")
    print("检查 HDFS 错误日志")
    print(f"{'='*60}")
    
    log_path = "/knowledge_graph/logs/pdf_extract_errors.log"
    cmd = ["docker", "exec", CONTAINER_NAME, "hadoop", "fs", "-test", "-e", log_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore')
    
    if result.returncode == 0:
        print(f"读取日志: {log_path}")
        cmd2 = ["docker", "exec", CONTAINER_NAME, "hadoop", "fs", "-cat", log_path]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        if result2.returncode == 0:
            print(result2.stdout)
        else:
            print(f"读取失败: {result2.stderr}")
    else:
        print(f"日志文件不存在: {log_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("Hadoop 任务日志检查工具")
    print("=" * 60)
    
    # 1. 列出最近的应用
    list_recent_applications()
    
    # 2. 查找容器日志
    find_container_logs()
    
    # 3. 检查 HDFS 错误日志
    check_hdfs_error_logs()
    
    print("\n" + "=" * 60)
    print("提示: 如果看到应用 ID，可以使用以下命令获取详细日志:")
    print("docker exec hadoop-namenode yarn logs -applicationId <app_id>")
    print("=" * 60)


if __name__ == "__main__":
    main()

