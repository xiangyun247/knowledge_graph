#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面诊断脚本：按照专业人士建议的5个问题逐一检查

使用方法：
python scripts/comprehensive_diagnosis.py <task_id>
"""

import sys
import subprocess
import json
import requests

BASE_URL = "http://127.0.0.1:5001"

def check_1_python_cache():
    """问题1: 检查 Python 模块缓存"""
    print("=" * 60)
    print("问题1: 检查 Python 模块缓存")
    print("=" * 60)
    
    # 检查容器内缓存
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "find", "/app", "-name", "*.pyc", "-o", "-name", "__pycache__"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    cache_files = [line for line in result.stdout.split('\n') if line.strip()]
    if cache_files:
        print(f"发现 {len(cache_files)} 个缓存文件/目录:")
        for f in cache_files[:10]:
            print(f"  - {f}")
        if len(cache_files) > 10:
            print(f"  ... 还有 {len(cache_files) - 10} 个")
        print("\n建议: 清除缓存")
        return False
    else:
        print("未发现缓存文件")
        return True

def check_2_exception_source(task_id):
    """问题2: 检查异常真正来源"""
    print("\n" + "=" * 60)
    print("问题2: 检查异常真正来源")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/hadoop/status/{task_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            task = data.get("task", {})
            
            has_traceback = "traceback" in task
            has_error_type = "error_type" in task
            has_debug = "debug" in task
            
            print(f"任务状态: {task.get('status')}")
            print(f"消息: {task.get('message')}")
            print(f"Hadoop 结果: {task.get('hadoop_result', {}).get('success')}")
            print(f"\n调试信息检查:")
            print(f"  traceback: {'YES' if has_traceback else 'NO'}")
            print(f"  error_type: {'YES' if has_error_type else 'NO'}")
            print(f"  debug: {'YES' if has_debug else 'NO'}")
            
            if has_traceback:
                print(f"\n完整 traceback:")
                print("-" * 60)
                print(task.get("traceback"))
                print("-" * 60)
            else:
                print("\n[WARNING] 缺少 traceback，无法定位异常来源")
                print("可能原因: 异常处理代码没有执行，或执行时出错")
            
            if has_debug:
                debug = task.get("debug", {})
                celery_modules = debug.get("celery_modules_loaded", [])
                if celery_modules:
                    print(f"\n已加载的 Celery 模块 ({len(celery_modules)} 个):")
                    for mod in celery_modules:
                        print(f"  - {mod.get('module')}: {mod.get('file')}")
                else:
                    print("\n未发现已加载的 Celery 模块")
            
            return has_traceback
        else:
            print(f"查询失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"查询失败: {e}")
        return False

def check_3_code_sync():
    """问题3: 检查 Docker volume 挂载代码同步"""
    print("\n" + "=" * 60)
    print("问题3: 检查 Docker volume 挂载代码同步")
    print("=" * 60)
    
    # 检查模块文件路径
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c",
         "import backend.hadoop_api as m; print(m.__file__)"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        module_file = result.stdout.strip()
        print(f"模块文件路径: {module_file}")
        
        if module_file == "/app/backend/hadoop_api.py":
            print("路径正确")
        else:
            print(f"[WARNING] 路径不正确，期望: /app/backend/hadoop_api.py")
            return False
        
        # 检查关键函数是否存在
        result2 = subprocess.run(
            ["docker", "exec", "kg-backend", "python", "-c",
             "import backend.hadoop_api as m; import inspect; "
             "func = getattr(m, '_run_hadoop_and_celery_in_background', None); "
             "print('Function exists:', func is not None); "
             "if func: src = inspect.getsource(func); "
             "print('Has fallback logic:', 'hadoop_ok' in src and 'Celery' in src)"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result2.returncode == 0:
            print(result2.stdout)
            return True
        else:
            print(f"检查失败: {result2.stderr}")
            return False
    else:
        print(f"检查失败: {result.stderr}")
        return False

def check_4_indirect_imports():
    """问题4: 检查间接导入"""
    print("\n" + "=" * 60)
    print("问题4: 检查间接导入")
    print("=" * 60)
    
    # 检查 sys.modules 中的 Celery 相关模块
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c",
         "import sys; "
         "celery_modules = [(name, getattr(mod, '__file__', None)) "
         "for name, mod in sys.modules.items() if 'celery' in name.lower()]; "
         "print('Celery modules in sys.modules:'); "
         "[print(f'{name}: {file}') for name, file in celery_modules]"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        output = result.stdout.strip()
        if output and "Celery modules" in output:
            print(output)
            return True
        else:
            print("未发现 Celery 相关模块在 sys.modules 中")
            print("这可能是好事（说明没有间接导入），也可能是问题（说明异常来自其他地方）")
            return True
    else:
        print(f"检查失败: {result.stderr}")
        return False

def check_5_celery_service():
    """问题5: 检查 Celery 服务初始化"""
    print("\n" + "=" * 60)
    print("问题5: 检查 Celery 服务初始化")
    print("=" * 60)
    
    # 检查 CeleryService 是否可以正常初始化
    result = subprocess.run(
        ["docker", "exec", "kg-backend", "python", "-c",
         "import sys; sys.path.insert(0, '/app'); "
         "from backend.celery_service import CeleryService; "
         "cs = CeleryService(); "
         "print(f'CeleryService initialized'); "
         "print(f'celery_app: {cs.celery_app}'); "
         "print(f'download_and_process_chunks: {cs.download_and_process_chunks}')"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print(f"初始化失败: {result.stderr}")
        return False

def main():
    if len(sys.argv) < 2:
        print("使用方法: python scripts/comprehensive_diagnosis.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    
    print("全面诊断开始")
    print("=" * 60)
    
    results = {}
    results["cache"] = check_1_python_cache()
    results["exception"] = check_2_exception_source(task_id)
    results["code_sync"] = check_3_code_sync()
    results["imports"] = check_4_indirect_imports()
    results["celery"] = check_5_celery_service()
    
    print("\n" + "=" * 60)
    print("诊断结果总结")
    print("=" * 60)
    for key, value in results.items():
        status = "PASS" if value else "FAIL"
        print(f"{key}: {status}")
    
    if not results["exception"]:
        print("\n[关键问题] 缺少 traceback，无法定位异常来源")
        print("建议: 检查后端日志，查看是否有异常处理的日志")

if __name__ == "__main__":
    main()

