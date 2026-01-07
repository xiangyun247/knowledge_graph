#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 mapper 脚本在 NodeManager 容器中的执行
"""

import subprocess
import sys

def test_mapper_script():
    """测试 mapper 脚本"""
    print("=" * 60)
    print("测试 mapper 脚本在 NodeManager 中的执行")
    print("=" * 60)
    
    # 1. 检查脚本是否存在
    print("\n1. 检查脚本文件...")
    mapper_path = "hadoop/mapreduce/pdf_extract/mapper.py"
    
    # 2. 复制脚本到 NodeManager
    print("\n2. 复制脚本到 NodeManager...")
    copy_cmd = [
        "docker", "cp", mapper_path, "hadoop-nodemanager:/tmp/mapper.py"
    ]
    result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"[FAIL] 复制脚本失败: {result.stderr}")
        return False
    print("[OK] 脚本已复制到 NodeManager")
    
    # 3. 测试脚本语法
    print("\n3. 检查脚本语法...")
    syntax_cmd = [
        "docker", "exec", "hadoop-nodemanager",
        "python3", "-m", "py_compile", "/tmp/mapper.py"
    ]
    result = subprocess.run(syntax_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"[FAIL] 脚本语法错误: {result.stderr}")
        return False
    print("[OK] 脚本语法正确")
    
    # 4. 测试导入依赖
    print("\n4. 测试导入依赖...")
    import_cmd = [
        "docker", "exec", "hadoop-nodemanager",
        "python3", "-c", "import sys; sys.path.insert(0, '/tmp'); import mapper; print('Import OK')"
    ]
    result = subprocess.run(import_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        print(f"[FAIL] 导入失败: {result.stderr}")
        print(f"标准输出: {result.stdout}")
        return False
    print("[OK] 脚本可以导入")
    
    # 5. 测试基本功能（模拟输入）
    print("\n5. 测试基本功能...")
    test_input = "/knowledge_graph/uploads/test/test.pdf"
    test_cmd = [
        "docker", "exec", "-i", "hadoop-nodemanager",
        "python3", "/tmp/mapper.py"
    ]
    result = subprocess.run(
        test_cmd,
        input=test_input + "\n",
        capture_output=True,
        text=True,
        timeout=60,
        encoding='utf-8',
        errors='ignore'
    )
    
    print(f"返回码: {result.returncode}")
    print(f"标准输出 (前500字符): {result.stdout[:500]}")
    print(f"标准错误 (前500字符): {result.stderr[:500]}")
    
    if result.returncode == 0:
        print("[OK] 脚本执行成功")
        return True
    else:
        print("[FAIL] 脚本执行失败")
        return False

if __name__ == "__main__":
    success = test_mapper_script()
    sys.exit(0 if success else 1)

