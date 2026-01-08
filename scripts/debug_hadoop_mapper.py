#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 Hadoop Mapper 脚本执行问题
"""

import subprocess
import sys

def check_mapper_script():
    """检查 mapper 脚本在 NodeManager 上的执行情况"""
    print("=" * 60)
    print("检查 Mapper 脚本执行环境")
    print("=" * 60)
    
    # 1. 检查 Python 路径
    print("\n1. 检查 Python 路径:")
    result = subprocess.run(
        ["docker", "exec", "hadoop-nodemanager", "which", "python3"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(f"   Python3 路径: {result.stdout.strip()}")
    else:
        print(f"   错误: {result.stderr.strip()}")
    
    # 2. 检查 Python 版本
    print("\n2. 检查 Python 版本:")
    result = subprocess.run(
        ["docker", "exec", "hadoop-nodemanager", "python3", "--version"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(f"   {result.stdout.strip()}")
    else:
        print(f"   错误: {result.stderr.strip()}")
    
    # 3. 检查 pdfplumber
    print("\n3. 检查 pdfplumber:")
    result = subprocess.run(
        ["docker", "exec", "hadoop-nodemanager", "python3", "-c", "import pdfplumber; print('pdfplumber version:', pdfplumber.__version__)"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(f"   {result.stdout.strip()}")
    else:
        print(f"   错误: {result.stderr.strip()}")
    
    # 4. 检查 mapper 脚本在 HDFS 上的内容
    print("\n4. 检查 mapper 脚本在 HDFS 上的内容:")
    result = subprocess.run(
        ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-cat", "/knowledge_graph/scripts/mapper.py"],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        print(f"   脚本行数: {len(lines)}")
        print(f"   第一行 (shebang): {lines[0] if lines else 'N/A'}")
    else:
        print(f"   错误: {result.stderr.strip()}")
    
    # 5. 测试 mapper 脚本语法
    print("\n5. 测试 mapper 脚本语法:")
    # 先下载脚本到本地
    result = subprocess.run(
        ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-get", "/knowledge_graph/scripts/mapper.py", "/tmp/test_mapper.py"],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        # 检查语法
        result2 = subprocess.run(
            ["docker", "exec", "hadoop-nodemanager", "python3", "-m", "py_compile", "/tmp/test_mapper.py"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result2.returncode == 0:
            print("   语法检查通过")
        else:
            print(f"   语法错误: {result2.stderr.strip()}")
    else:
        print(f"   下载脚本失败: {result.stderr.strip()}")
    
    # 6. 测试简单的 mapper 执行
    print("\n6. 测试简单的 mapper 执行:")
    test_input = "/knowledge_graph/uploads/test/test.pdf"
    test_cmd = f"echo '{test_input}' | /usr/local/bin/python3 /tmp/test_mapper.py"
    result = subprocess.run(
        ["docker", "exec", "hadoop-nodemanager", "sh", "-c", test_cmd],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        print(f"   执行成功")
        print(f"   输出: {result.stdout.strip()[:200]}")
    else:
        print(f"   执行失败 (返回码: {result.returncode})")
        print(f"   错误: {result.stderr.strip()[:500]}")


if __name__ == "__main__":
    check_mapper_script()

