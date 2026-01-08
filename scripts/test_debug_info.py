#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证 hadoop_api.py 中的调试信息收集功能

使用方法：
python scripts/test_debug_info.py
"""

import requests
import json
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:5001"

def test_debug_info():
    """测试调试信息收集功能"""
    print("=" * 60)
    print("测试调试信息收集功能")
    print("=" * 60)
    
    # 1. 检查容器内代码版本
    print("\n【步骤 1】检查容器内代码版本")
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c", 
         "import backend.hadoop_api as m; import inspect; "
         "print(f'模块文件: {m.__file__}'); "
         "print('\\n_collect_celery_debug_info 函数源码:'); "
         "print(inspect.getsource(m._collect_celery_debug_info))"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"检查失败: {result.stderr}")
    
    # 2. 运行批处理测试（如果有测试文件）
    print("\n【步骤 2】运行批处理测试")
    print("提示：请先运行 python tests/test_batch_build.py 获取 task_id")
    
    task_id = input("请输入 task_id（或按 Enter 跳过）: ").strip()
    
    if not task_id:
        print("跳过批处理测试")
        return
    
    # 3. 查询任务状态并显示调试信息
    print(f"\n【步骤 3】查询任务状态: {task_id}")
    try:
        response = requests.get(f"{BASE_URL}/api/hadoop/status/{task_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            task = data.get("task", {})
            
            print(f"\n任务状态: {task.get('status')}")
            print(f"进度: {task.get('progress')}%")
            print(f"消息: {task.get('message')}")
            
            # 显示异常信息
            if "error_type" in task:
                print(f"\n异常类型: {task.get('error_type')}")
                print(f"异常消息: {task.get('error_message')}")
            
            # 显示完整 traceback
            if "traceback" in task:
                print(f"\n完整调用栈:")
                print("-" * 60)
                print(task.get('traceback'))
                print("-" * 60)
            
            # 显示调试信息
            if "debug" in task:
                debug = task.get("debug", {})
                print(f"\n调试信息:")
                print(f"Python 版本: {debug.get('python', 'N/A')}")
                
                celery_modules = debug.get("celery_modules_loaded", [])
                if celery_modules:
                    print(f"\n已加载的 Celery 相关模块 ({len(celery_modules)} 个):")
                    for mod_info in celery_modules:
                        print(f"  - {mod_info.get('module')}")
                        print(f"    文件路径: {mod_info.get('file', 'N/A')}")
                else:
                    print("\n未发现已加载的 Celery 相关模块")
            
            # 保存完整信息到文件
            output_file = f"debug_info_{task_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n完整调试信息已保存到: {output_file}")
            
        else:
            print(f"查询失败: HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"查询失败: {e}")

if __name__ == "__main__":
    test_debug_info()

