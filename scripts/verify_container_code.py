#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证脚本：检查容器内代码版本是否与本地一致

使用方法：
python scripts/verify_container_code.py
"""

import subprocess
import sys
import os

def check_container_code():
    """检查容器内的代码版本"""
    print("=" * 60)
    print("检查容器内代码版本")
    print("=" * 60)
    
    # 检查关键函数是否存在
    checks = [
        ("_collect_celery_debug_info", "检查调试信息收集函数"),
        ("_run_hadoop_and_celery_in_background", "检查后台任务函数"),
    ]
    
    for func_name, description in checks:
        print(f"\n{description}: {func_name}")
        result = subprocess.run(
            ["docker", "exec", "kg-backend", "python", "-c", 
             f"import backend.hadoop_api as m; import inspect; "
             f"func = getattr(m, '{func_name}', None); "
             f"print('✓ 函数存在' if func else '✗ 函数不存在'); "
             f"if func: print('源码前 5 行:'); "
             f"print('\\n'.join(inspect.getsource(func).split('\\n')[:5]))"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"检查失败: {result.stderr}")
    
    # 检查模块文件路径
    print("\n检查模块文件路径:")
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c", 
         "import backend.hadoop_api as m; print(f'模块文件: {m.__file__}')"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(result.stdout)
        file_path = result.stdout.strip().split(": ")[-1] if ": " in result.stdout else None
        if file_path:
            print(f"\n检查文件是否存在:")
            result2 = subprocess.run(
                ["docker", "exec", "kg-backend", "test", "-f", file_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result2.returncode == 0:
                print(f"✓ 文件存在: {file_path}")
            else:
                print(f"✗ 文件不存在: {file_path}")
    else:
        print(f"检查失败: {result.stderr}")
    
    # 检查异常处理代码
    print("\n检查异常处理代码（应包含调试信息收集）:")
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c", 
         "import backend.hadoop_api as m; import inspect; "
         "src = inspect.getsource(m._run_hadoop_and_celery_in_background); "
         "has_debug = '_collect_celery_debug_info' in src; "
         "has_traceback = 'traceback.format_exc' in src; "
         "has_error_type = 'error_type' in src; "
         "print(f'包含调试信息收集: {\"✓\" if has_debug else \"✗\"}'); "
         "print(f'包含 traceback: {\"✓\" if has_traceback else \"✗\"}'); "
         "print(f'包含 error_type: {\"✓\" if has_error_type else \"✗\"}')"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"检查失败: {result.stderr}")

if __name__ == "__main__":
    check_container_code()

