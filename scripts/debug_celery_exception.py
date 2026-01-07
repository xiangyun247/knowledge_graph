#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：追踪 "Celery 任务未初始化" 异常的来源

使用方法：
1. 在容器内运行：docker exec kg-backend python /app/scripts/debug_celery_exception.py
2. 或者在本地运行（需要设置正确的环境变量）
"""

import sys
import traceback
import importlib

def check_module_imports(module_name):
    """检查模块的导入链"""
    print(f"\n=== 检查模块: {module_name} ===")
    try:
        # 清除模块缓存
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # 尝试导入
        module = importlib.import_module(module_name)
        print(f"✓ 成功导入: {module_name}")
        
        # 检查模块的属性
        if hasattr(module, '__file__'):
            print(f"  文件位置: {module.__file__}")
        
        # 检查是否导入了 Celery 相关模块
        for attr_name in dir(module):
            if 'celery' in attr_name.lower():
                attr = getattr(module, attr_name)
                print(f"  发现 Celery 相关属性: {attr_name} = {type(attr)}")
        
        return True
    except Exception as e:
        print(f"✗ 导入失败: {module_name}")
        print(f"  错误: {e}")
        traceback.print_exc()
        return False

def test_hadoop_service():
    """测试 Hadoop 服务初始化"""
    print("\n=== 测试 Hadoop 服务初始化 ===")
    try:
        from backend.hadoop_service import get_hadoop_service
        service = get_hadoop_service()
        print("✓ Hadoop 服务初始化成功")
        return True
    except Exception as e:
        print(f"✗ Hadoop 服务初始化失败: {e}")
        traceback.print_exc()
        return False

def test_celery_service():
    """测试 Celery 服务初始化"""
    print("\n=== 测试 Celery 服务初始化 ===")
    try:
        from backend.celery_service import get_celery_service
        service = get_celery_service()
        print("✓ Celery 服务初始化成功")
        print(f"  celery_app: {service.celery_app}")
        print(f"  download_and_process_chunks: {service.download_and_process_chunks}")
        return True
    except Exception as e:
        print(f"✗ Celery 服务初始化失败: {e}")
        traceback.print_exc()
        return False

def test_hadoop_api_import():
    """测试 hadoop_api 模块导入"""
    print("\n=== 测试 hadoop_api 模块导入 ===")
    try:
        # 清除缓存
        modules_to_clear = [
            'backend.hadoop_api',
            'backend.hadoop_service',
            'backend.celery_service',
            'backend.app',
        ]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]
        
        from backend.hadoop_api import router, _run_hadoop_and_celery_in_background
        print("✓ hadoop_api 模块导入成功")
        print(f"  router: {router}")
        print(f"  _run_hadoop_and_celery_in_background: {_run_hadoop_and_celery_in_background}")
        return True
    except Exception as e:
        print(f"✗ hadoop_api 模块导入失败: {e}")
        traceback.print_exc()
        return False

def test_app_globals():
    """测试 _get_app_globals 函数"""
    print("\n=== 测试 _get_app_globals 函数 ===")
    try:
        from backend.hadoop_api import _get_app_globals
        globals_ = _get_app_globals()
        print("✓ _get_app_globals 调用成功")
        print(f"  返回的键: {list(globals_.keys())}")
        return True
    except Exception as e:
        print(f"✗ _get_app_globals 调用失败: {e}")
        traceback.print_exc()
        return False

def check_all_imports():
    """检查所有相关模块的导入"""
    modules = [
        'backend.hadoop_api',
        'backend.hadoop_service',
        'backend.celery_service',
        'backend.celery_app',
        'backend.celery_tasks',
        'backend.app',
    ]
    
    results = {}
    for module_name in modules:
        results[module_name] = check_module_imports(module_name)
    
    return results

def main():
    print("=" * 60)
    print("Celery 异常调试脚本")
    print("=" * 60)
    
    # 1. 检查所有模块导入
    print("\n【步骤 1】检查所有相关模块的导入")
    import_results = check_all_imports()
    
    # 2. 测试各个服务初始化
    print("\n【步骤 2】测试服务初始化")
    test_hadoop_service()
    test_celery_service()
    
    # 3. 测试 hadoop_api 导入
    print("\n【步骤 3】测试 hadoop_api 模块导入")
    test_hadoop_api_import()
    
    # 4. 测试 _get_app_globals
    print("\n【步骤 4】测试 _get_app_globals 函数")
    test_app_globals()
    
    # 5. 检查 Python 缓存
    print("\n【步骤 5】检查 Python 缓存")
    import os
    cache_dirs = []
    for root, dirs, files in os.walk('/app'):
        if '__pycache__' in dirs:
            cache_dirs.append(os.path.join(root, '__pycache__'))
        for file in files:
            if file.endswith('.pyc'):
                cache_dirs.append(os.path.join(root, file))
    
    if cache_dirs:
        print(f"发现 {len(cache_dirs)} 个缓存文件/目录:")
        for cache in cache_dirs[:10]:  # 只显示前10个
            print(f"  - {cache}")
        if len(cache_dirs) > 10:
            print(f"  ... 还有 {len(cache_dirs) - 10} 个")
    else:
        print("未发现缓存文件")
    
    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()

