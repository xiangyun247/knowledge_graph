#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试 PDF 提取 mapper

在 NodeManager 容器中直接运行 mapper 脚本，模拟 Hadoop Streaming 环境
"""

import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTAINER_NAME = "hadoop-nodemanager"
MAPPER_SCRIPT = "hadoop/mapreduce/pdf_extract/mapper.py"


def test_mapper_with_hdfs_path(hdfs_path):
    """使用真实的 HDFS 路径测试 mapper"""
    print("=" * 60)
    print(f"测试 PDF 提取 mapper")
    print(f"HDFS 路径: {hdfs_path}")
    print("=" * 60)
    
    # 1. 复制脚本到容器
    mapper_local = os.path.join(PROJECT_ROOT, MAPPER_SCRIPT)
    container_mapper = "/tmp/mapper.py"
    
    print("\n1. 复制脚本到容器...")
    result = subprocess.run(
        ["docker", "cp", mapper_local, f"{CONTAINER_NAME}:{container_mapper}"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode != 0:
        print(f"[FAIL] 复制失败: {result.stderr}")
        return False
    
    print("[OK] 脚本已复制")
    
    # 2. 设置可执行权限
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "chmod", "+x", container_mapper],
        capture_output=True,
        timeout=10
    )
    
    # 3. 运行 mapper（模拟 Hadoop Streaming 输入）
    print(f"\n2. 运行 mapper 脚本...")
    print(f"输入: {hdfs_path}")
    
    result = subprocess.run(
        ["docker", "exec", "-i", CONTAINER_NAME, "python3", container_mapper],
        input=f"{hdfs_path}\n",
        capture_output=True,
        text=True,
        timeout=300,
        encoding='utf-8',
        errors='ignore'
    )
    
    # 4. 显示结果
    print(f"\n3. 执行结果:")
    print(f"返回码: {result.returncode}")
    
    if result.stdout:
        print(f"\n标准输出 (前1000字符):")
        print(result.stdout[:1000])
    
    if result.stderr:
        print(f"\n标准错误 (前1000字符):")
        print(result.stderr[:1000])
    
    # 5. 清理
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "rm", "-f", container_mapper],
        capture_output=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print("\n[OK] Mapper 执行成功")
        return True
    else:
        print("\n[FAIL] Mapper 执行失败")
        return False


def main():
    """主函数"""
    if len(sys.argv) > 1:
        hdfs_path = sys.argv[1]
    else:
        # 使用最近上传的文件
        print("未提供 HDFS 路径，尝试查找最近上传的文件...")
        
        # 列出上传目录
        result = subprocess.run(
            ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-ls", "/knowledge_graph/uploads"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0:
            print(result.stdout)
            print("\n请提供一个 HDFS 路径作为参数，例如:")
            print("python scripts/test_pdf_extract_mapper_direct.py /knowledge_graph/uploads/xxx/file.pdf")
            return
        else:
            print("无法列出上传目录")
            return
    
    success = test_mapper_with_hdfs_path(hdfs_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

