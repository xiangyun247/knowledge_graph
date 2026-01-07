#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整端到端测试脚本
包括环境检查、基础测试和完整流程测试
"""

import sys
import subprocess
import time
from pathlib import Path

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def check_services():
    """检查所有服务是否运行"""
    print_header("步骤 1: 检查服务状态")
    
    services = [
        "hadoop-namenode",
        "hadoop-datanode", 
        "hadoop-resourcemanager",
        "kg-redis",
        "kg-neo4j",
        "kg-mysql",
        "kg-celery-worker"
    ]
    
    all_running = True
    for service in services:
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if service in result.stdout:
                print(f"  [OK] {service}: 运行中")
            else:
                print(f"  [WARN] {service}: 未运行")
                if service != "hadoop-nodemanager":  # NodeManager 是可选的
                    all_running = False
        except Exception as e:
            print(f"  [FAIL] 检查 {service} 失败: {e}")
            all_running = False
    
    return all_running

def run_basic_tests():
    """运行基础集成测试"""
    print_header("步骤 2: 运行基础集成测试")
    
    try:
        result = subprocess.run(
            [sys.executable, "scripts/test_hadoop_integration.py"],
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='ignore'
        )
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"  [FAIL] 基础测试失败: {e}")
        return False

def check_backend():
    """检查后端服务"""
    print_header("步骤 3: 检查后端服务")
    
    try:
        import requests
        response = requests.get("http://localhost:5001/docs", timeout=5)
        if response.status_code == 200:
            print("  [OK] 后端服务运行正常 (http://localhost:5001)")
            return True
        else:
            print(f"  [WARN] 后端服务响应异常: {response.status_code}")
            return False
    except ImportError:
        print("  [WARN] requests 库未安装，跳过后端检查")
        return True
    except Exception as e:
        print(f"  [FAIL] 后端服务检查失败: {e}")
        print("  提示: 请确保后端服务已启动 (python run.py)")
        return False

def check_pdf_files():
    """检查测试 PDF 文件"""
    print_header("步骤 4: 检查测试 PDF 文件")
    
    pdf_files = [
        r"C:\Users\23035\Desktop\pdf_test1.pdf",
        r"C:\Users\23035\Desktop\pdf_test2.pdf"
    ]
    
    found_files = []
    for pdf_file in pdf_files:
        path = Path(pdf_file)
        if path.exists():
            print(f"  [OK] 找到: {pdf_file}")
            found_files.append(pdf_file)
        else:
            print(f"  [WARN] 未找到: {pdf_file}")
    
    if found_files:
        print(f"\n  [INFO] 找到 {len(found_files)} 个测试 PDF 文件")
        return found_files
    else:
        print("\n  [WARN] 未找到测试 PDF 文件")
        print("  提示: 可以将 PDF 文件放在以下位置:")
        print("    - C:\\Users\\23035\\Desktop\\pdf_test1.pdf")
        print("    - C:\\Users\\23035\\Desktop\\pdf_test2.pdf")
        print("    或修改 tests/test_batch_build.py 中的 PDF_FILES 路径")
        return None

def run_full_test(pdf_files=None):
    """运行完整端到端测试"""
    if not pdf_files:
        print_header("步骤 5: 跳过完整测试（无 PDF 文件）")
        print("  要运行完整测试，请准备测试 PDF 文件并运行:")
        print("    python tests/test_batch_build.py")
        return True
    
    print_header("步骤 5: 运行完整端到端测试")
    print("  这将执行:")
    print("    1. 批量上传 PDF 文件到 HDFS")
    print("    2. Hadoop MapReduce 处理 (PDF提取 → 文本清洗 → 文本分块)")
    print("    3. Celery 任务构建知识图谱")
    print("    4. 轮询任务状态直到完成")
    print("\n  这可能需要几分钟时间...\n")
    
    try:
        result = subprocess.run(
            [sys.executable, "tests/test_batch_build.py"],
            timeout=1800,  # 30分钟超时
            encoding='utf-8',
            errors='ignore'
        )
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("  ⚠️  测试超时（30分钟）")
        return False
    except Exception as e:
        print(f"  ❌ 完整测试失败: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  Hadoop 集成完整测试")
    print("=" * 70)
    
    results = {}
    
    # 步骤 1: 检查服务
    results["服务检查"] = check_services()
    
    # 步骤 2: 基础测试
    if results["服务检查"]:
        results["基础测试"] = run_basic_tests()
    else:
        print("\n  ⚠️  部分服务未运行，跳过基础测试")
        results["基础测试"] = False
    
    # 步骤 3: 检查后端
    results["后端服务"] = check_backend()
    
    # 步骤 4: 检查 PDF 文件
    pdf_files = check_pdf_files()
    
    # 步骤 5: 完整测试
    if results["后端服务"] and pdf_files:
        results["完整测试"] = run_full_test(pdf_files)
    else:
        results["完整测试"] = None
    
    # 总结
    print_header("测试总结")
    
    for test_name, result in results.items():
        if result is None:
            status = "[SKIP] 跳过"
        elif result:
            status = "[PASS] 通过"
        else:
            status = "[FAIL] 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(r for r in results.values() if r is not None)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("  [SUCCESS] 所有测试通过！Hadoop 集成正常工作。")
        return 0
    else:
        print("  [WARN] 部分测试失败或跳过，请检查上述信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

