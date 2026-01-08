#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Celery应用初始化
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("开始测试Celery应用初始化...")

try:
    # 导入Celery应用
    from backend.celery import app
    print("✓ 成功导入Celery应用")
    print(f"Celery应用名称: {app.main}")
    print(f"Celery任务队列: {app.conf.task_queues}")
    print(f"Celery任务路由: {app.conf.task_routes}")
    print(f"Celery结果后端: {app.conf.result_backend}")
    print(f"Celery代理URL: {app.conf.broker_url}")
    
    # 手动导入tasks模块，确保任务被注册
    import backend.tasks
    
    # 尝试获取已注册的任务
    tasks = app.tasks
    print(f"\n已注册的任务列表:")
    for task_name in tasks:
        if task_name.startswith('backend.'):
            print(f"  - {task_name}")
    
    # 检查是否有任务被注册
    has_backend_tasks = any(task_name.startswith('backend.') for task_name in tasks)
    if has_backend_tasks:
        print("\n✓ Celery应用初始化测试成功!")
    else:
        print("\n⚠️  Celery应用初始化成功，但没有发现任务!")
    
except Exception as e:
    print(f"✗ Celery应用初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
