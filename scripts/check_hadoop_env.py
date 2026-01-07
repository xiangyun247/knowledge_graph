#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hadoop 环境检查和诊断脚本
用于验证 Hadoop 环境是否配置正确
"""

import os
import subprocess
import sys
from pathlib import Path

def check_docker():
    """检查 Docker 是否可用"""
    print("=" * 60)
    print("1. 检查 Docker 环境")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"[OK] Docker 已安装: {result.stdout.strip()}")
            return True
        else:
            print("[FAIL] Docker 未正确安装")
            return False
    except FileNotFoundError:
        print("[FAIL] Docker 未安装或不在 PATH 中")
        return False
    except Exception as e:
        print(f"[FAIL] Docker 检查失败: {e}")
        return False

def check_hadoop_containers():
    """检查 Hadoop 容器是否运行"""
    print("\n" + "=" * 60)
    print("2. 检查 Hadoop 容器状态")
    print("=" * 60)
    
    containers = [
        "hadoop-namenode",
        "hadoop-datanode",
        "hadoop-resourcemanager",
        "hadoop-nodemanager"
    ]
    
    all_running = True
    for container in containers:
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}: {{.Status}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if container in result.stdout:
                print(f"[OK] {container}: 运行中")
            else:
                print(f"[FAIL] {container}: 未运行")
                all_running = False
        except Exception as e:
            print(f"[FAIL] 检查 {container} 失败: {e}")
            all_running = False
    
    return all_running

def check_hdfs_connection():
    """检查 HDFS 连接"""
    print("\n" + "=" * 60)
    print("3. 检查 HDFS 连接")
    print("=" * 60)
    
    try:
        # 测试 HDFS 命令
        result = subprocess.run(
            ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-ls", "/"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("[OK] HDFS 连接成功")
            print(f"  根目录内容:\n{result.stdout[:200]}")
            return True
        else:
            print(f"[FAIL] HDFS 连接失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[FAIL] HDFS 连接检查失败: {e}")
        return False

def check_streaming_jar():
    """检查 Hadoop Streaming JAR 是否存在"""
    print("\n" + "=" * 60)
    print("4. 检查 Hadoop Streaming JAR")
    print("=" * 60)
    
    possible_paths = [
        "/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar",
        "/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming.jar",
    ]
    
    for jar_path in possible_paths:
        try:
            result = subprocess.run(
                ["docker", "exec", "hadoop-namenode", "test", "-f", jar_path],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"[OK] 找到 Streaming JAR: {jar_path}")
                return jar_path
        except Exception as e:
            continue
    
    print("[FAIL] 未找到 Hadoop Streaming JAR")
    return None

def check_python_dependencies():
    """检查 Python 依赖（在容器中）"""
    print("\n" + "=" * 60)
    print("5. 检查 Python 依赖（在 Hadoop 容器中）")
    print("=" * 60)
    
    dependencies = ["python3", "pdfplumber"]
    
    for dep in dependencies:
        try:
            if dep == "python3":
                result = subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "which", dep],
                    capture_output=True,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "python3", "-c", f"import {dep}"],
                    capture_output=True,
                    timeout=5
                )
            
            if result.returncode == 0:
                print(f"[OK] {dep}: 已安装")
            else:
                print(f"[FAIL] {dep}: 未安装")
                if dep == "pdfplumber":
                    print(f"  提示: 需要在容器中安装: pip install {dep}")
        except Exception as e:
            print(f"[FAIL] 检查 {dep} 失败: {e}")

def check_mapreduce_scripts():
    """检查 MapReduce 脚本是否存在"""
    print("\n" + "=" * 60)
    print("6. 检查 MapReduce 脚本")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    scripts = [
        "hadoop/mapreduce/pdf_extract/mapper.py",
        "hadoop/mapreduce/pdf_extract/reducer.py",
        "hadoop/mapreduce/text_clean/mapper.py",
        "hadoop/mapreduce/text_chunk/mapper.py",
    ]
    
    all_exist = True
    for script in scripts:
        script_path = project_root / script
        if script_path.exists():
            print(f"[OK] {script}: 存在")
        else:
            print(f"[FAIL] {script}: 不存在")
            all_exist = False
    
    return all_exist

def check_hadoop_config():
    """检查 Hadoop 配置文件"""
    print("\n" + "=" * 60)
    print("7. 检查 Hadoop 配置文件")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    configs = [
        "hadoop/config/core-site.xml",
        "hadoop/config/hdfs-site.xml",
        "hadoop/config/mapred-site.xml",
        "hadoop/config/yarn-site.xml",
    ]
    
    all_exist = True
    for config in configs:
        config_path = project_root / config
        if config_path.exists():
            print(f"[OK] {config}: 存在")
            
            # 检查是否有重复配置
            try:
                content = config_path.read_text(encoding='utf-8')
                # 简单检查：如果某个 property 出现多次，可能有问题
                if "fs.defaultFS" in content:
                    count = content.count("<name>fs.defaultFS</name>")
                    if count > 1:
                        print(f"  [WARN] fs.defaultFS 配置出现 {count} 次（可能有重复）")
            except Exception as e:
                print(f"  [WARN] 无法读取配置文件: {e}")
        else:
            print(f"[FAIL] {config}: 不存在")
            all_exist = False
    
    return all_exist

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Hadoop 环境诊断工具")
    print("=" * 60 + "\n")
    
    results = {
        "Docker": check_docker(),
        "Hadoop 容器": check_hadoop_containers(),
        "HDFS 连接": check_hdfs_connection(),
        "Streaming JAR": check_streaming_jar() is not None,
        "MapReduce 脚本": check_mapreduce_scripts(),
        "Hadoop 配置": check_hadoop_config(),
    }
    
    check_python_dependencies()
    
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "[OK] 通过" if passed else "[FAIL] 失败"
        print(f"{check_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[OK] 所有检查通过！Hadoop 环境配置正常。")
        return 0
    else:
        print("\n[FAIL] 部分检查失败，请根据上述提示修复问题。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

