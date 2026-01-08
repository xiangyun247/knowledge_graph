#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 mapper 脚本执行
"""

import subprocess
import sys

def test_mapper_in_nodemanager():
    """在 NodeManager 容器中测试 mapper 脚本"""
    print("=" * 60)
    print("测试 mapper 脚本执行")
    print("=" * 60)
    
    # 1. 检查 mapper 脚本是否存在
    mapper_path = "hadoop/mapreduce/pdf_extract/mapper.py"
    print(f"\n1. 检查 mapper 脚本: {mapper_path}")
    
    # 2. 将 mapper 脚本复制到 NodeManager 容器
    print("\n2. 复制 mapper 脚本到 NodeManager 容器...")
    copy_cmd = [
        "docker", "cp", mapper_path, "hadoop-nodemanager:/tmp/test_mapper.py"
    ]
    result = subprocess.run(copy_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   [FAIL] 复制失败: {result.stderr}")
        return False
    print("   [OK] 复制成功")
    
    # 3. 设置执行权限
    print("\n3. 设置执行权限...")
    chmod_cmd = ["docker", "exec", "hadoop-nodemanager", "chmod", "+x", "/tmp/test_mapper.py"]
    result = subprocess.run(chmod_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   [FAIL] 设置权限失败: {result.stderr}")
        return False
    print("   [OK] 权限设置成功")
    
    # 4. 测试直接执行 mapper 脚本（使用 shebang）
    print("\n4. 测试直接执行 mapper 脚本（使用 shebang）...")
    test_input = "/knowledge_graph/uploads/test/test.pdf\n"
    exec_cmd = [
        "docker", "exec", "-i", "hadoop-nodemanager",
        "/tmp/test_mapper.py"
    ]
    result = subprocess.run(
        exec_cmd,
        input=test_input,
        capture_output=True,
        text=True,
        timeout=30
    )
    print(f"   返回码: {result.returncode}")
    if result.stdout:
        print(f"   标准输出: {result.stdout[:500]}")
    if result.stderr:
        print(f"   标准错误: {result.stderr[:500]}")
    
    # 5. 测试使用 python3 执行 mapper 脚本
    print("\n5. 测试使用 python3 执行 mapper 脚本...")
    exec_cmd2 = [
        "docker", "exec", "-i", "hadoop-nodemanager",
        "/usr/local/bin/python3", "/tmp/test_mapper.py"
    ]
    result2 = subprocess.run(
        exec_cmd2,
        input=test_input,
        capture_output=True,
        text=True,
        timeout=30
    )
    print(f"   返回码: {result2.returncode}")
    if result2.stdout:
        print(f"   标准输出: {result2.stdout[:500]}")
    if result2.stderr:
        print(f"   标准错误: {result2.stderr[:500]}")
    
    # 6. 测试导入 mapper 模块
    print("\n6. 测试导入 mapper 模块...")
    import_cmd = [
        "docker", "exec", "hadoop-nodemanager",
        "/usr/local/bin/python3", "-c",
        "import sys; sys.path.insert(0, '/tmp'); "
        "try: "
        "  import test_mapper as m; "
        "  print('Import successful'); "
        "  print('Has mapper function:', hasattr(m, 'mapper')); "
        "  print('Has extract_pdf_text:', hasattr(m, 'extract_pdf_text'))"
        "except Exception as e: "
        "  import traceback; "
        "  print('Import failed:'); "
        "  traceback.print_exc()"
    ]
    result3 = subprocess.run(import_cmd, capture_output=True, text=True, timeout=30)
    print(f"   返回码: {result3.returncode}")
    if result3.stdout:
        print(f"   输出: {result3.stdout}")
    if result3.stderr:
        print(f"   错误: {result3.stderr}")
    
    return True


if __name__ == "__main__":
    test_mapper_in_nodemanager()

