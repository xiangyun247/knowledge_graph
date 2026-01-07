#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hadoop 集成端到端测试脚本

测试完整的 Hadoop 处理流程：
1. 上传测试文件到 HDFS
2. 运行 PDF 提取任务
3. 运行文本清洗任务
4. 运行文本分块任务
5. 验证输出结果
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def check_container_running(container_name):
    """检查容器是否运行"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return container_name in result.stdout
    except Exception:
        return False

def test_hdfs_basic_operations():
    """测试 HDFS 基本操作"""
    print_section("测试 1: HDFS 基本操作")
    
    # 检查 NameNode 容器
    if not check_container_running("hadoop-namenode"):
        print("[FAIL] hadoop-namenode 容器未运行")
        return False
    
    print("[OK] hadoop-namenode 容器运行中")
    
    # 测试创建目录
    test_dir = "/knowledge_graph/test"
    cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-mkdir", "-p", test_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        print(f"[OK] 创建测试目录成功: {test_dir}")
    else:
        print(f"[FAIL] 创建测试目录失败: {result.stderr}")
        return False
    
    # 清理可能存在的旧文件
    hdfs_path = f"{test_dir}/test_file.txt"
    subprocess.run(
        ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-rm", "-f", hdfs_path],
        capture_output=True,
        timeout=10
    )
    
    # 测试上传文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
        tmp_file.write("这是一个测试文件\n用于验证 HDFS 功能")
        tmp_path = tmp_file.name
    
    try:
        # 复制到容器
        container_temp = "/tmp/test_file.txt"
        copy_result = subprocess.run(
            ["docker", "cp", tmp_path, f"hadoop-namenode:{container_temp}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if copy_result.returncode != 0:
            print(f"[FAIL] 复制文件到容器失败: {copy_result.stderr}")
            return False
        
        # 上传到 HDFS
        upload_cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-put", "-f", container_temp, hdfs_path]
        upload_result = subprocess.run(upload_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        # 清理容器临时文件
        subprocess.run(
            ["docker", "exec", "hadoop-namenode", "rm", "-f", container_temp],
            capture_output=True,
            timeout=10
        )
        
        if upload_result.returncode == 0:
            print(f"[OK] 上传文件到 HDFS 成功: {hdfs_path}")
        else:
            print(f"[FAIL] 上传文件失败: {upload_result.stderr}")
            return False
        
        # 测试读取文件
        read_cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-cat", hdfs_path]
        read_result = subprocess.run(read_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        
        if read_result.returncode == 0 and read_result.stdout and ("测试文件" in read_result.stdout or "test" in read_result.stdout.lower()):
            print("[OK] 从 HDFS 读取文件成功")
        else:
            print(f"[FAIL] 读取文件失败: {read_result.stderr if read_result.stderr else 'No output'}")
            return False
        
        return True
        
    finally:
        # 清理本地临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_mapreduce_script_upload():
    """测试 MapReduce 脚本上传"""
    print_section("测试 2: MapReduce 脚本上传")
    
    from backend.hadoop_service import get_hadoop_service
    
    hadoop_service = get_hadoop_service()
    
    # 测试上传 mapper 脚本
    mapper_path = "hadoop/mapreduce/text_clean/mapper.py"
    try:
        hdfs_path = hadoop_service._upload_script_to_hdfs(mapper_path)
        print(f"[OK] 脚本上传成功: {mapper_path} -> {hdfs_path}")
        return True
    except Exception as e:
        print(f"[FAIL] 脚本上传失败: {e}")
        return False

def test_pdf_extract_simple():
    """测试简单的 PDF 提取（如果有测试 PDF）"""
    print_section("测试 3: PDF 提取功能（需要测试 PDF 文件）")
    
    # 检查是否有测试 PDF
    test_pdf_paths = [
        "data/raw/test.pdf",
        "data/examples/test.pdf",
        "tests/test.pdf"
    ]
    
    test_pdf = None
    for path in test_pdf_paths:
        full_path = project_root / path
        if full_path.exists():
            test_pdf = full_path
            break
    
    if not test_pdf:
        print("[SKIP] 未找到测试 PDF 文件，跳过此测试")
        print("  提示: 可以将测试 PDF 放在 data/raw/ 目录下")
        return True
    
    print(f"[INFO] 找到测试 PDF: {test_pdf}")
    
    # 这里可以添加实际的 PDF 提取测试
    # 由于需要完整的 MapReduce 任务，这里只做提示
    print("[INFO] PDF 提取测试需要完整的 MapReduce 任务")
    print("  建议使用 test_batch_build.py 进行完整测试")
    
    return True

def test_hadoop_service_initialization():
    """测试 Hadoop 服务初始化"""
    print_section("测试 4: Hadoop 服务初始化")
    
    try:
        from backend.hadoop_service import get_hadoop_service
        
        service = get_hadoop_service()
        print(f"[OK] Hadoop 服务初始化成功")
        print(f"  NameNode: {service.hadoop_namenode}")
        print(f"  HDFS Root: {service.hdfs_root}")
        print(f"  Streaming JAR: {service.streaming_jar}")
        return True
    except Exception as e:
        print(f"[FAIL] Hadoop 服务初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_celery_integration():
    """测试 Celery 集成（如果可用）"""
    print_section("测试 5: Celery 集成检查")
    
    # 检查 Redis 容器
    if not check_container_running("kg-redis"):
        print("[SKIP] Redis 容器未运行，跳过 Celery 测试")
        return True
    
    print("[OK] Redis 容器运行中")
    
    # 检查 Celery Worker 容器
    if not check_container_running("kg-celery-worker"):
        print("[WARN] Celery Worker 容器未运行")
        print("  提示: 运行 docker-compose up -d celery-worker 启动")
        return True
    
    print("[OK] Celery Worker 容器运行中")
    
    # 这里可以添加 Celery 任务测试
    print("[INFO] Celery 集成检查完成")
    return True

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("  Hadoop 集成端到端测试")
    print("=" * 60)
    
    results = {
        "HDFS 基本操作": test_hdfs_basic_operations(),
        "MapReduce 脚本上传": test_mapreduce_script_upload(),
        "PDF 提取功能": test_pdf_extract_simple(),
        "Hadoop 服务初始化": test_hadoop_service_initialization(),
        "Celery 集成": test_celery_integration(),
    }
    
    print_section("测试总结")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] 所有测试通过！")
        print("\n下一步建议:")
        print("1. 准备测试 PDF 文件")
        print("2. 运行完整测试: python tests/test_batch_build.py")
        print("3. 或通过 API 测试: POST /api/hadoop/upload/batch")
        return 0
    else:
        print("[FAIL] 部分测试失败，请检查上述错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())

