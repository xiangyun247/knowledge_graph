#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 应用配置文件
"""

import os
from celery import Celery

# 设置环境变量，确保Django或其他框架的设置能被正确加载
# 这里我们使用简单的配置，不依赖Django
os.environ.setdefault('CELERY_CONFIG_MODULE', 'backend.celeryconfig')

# 创建Celery应用实例
app = Celery('knowledge_graph')

# 加载配置
app.config_from_object('backend.celeryconfig')

# 自动发现任务
# 这会搜索所有已安装的应用中的tasks.py文件
app.autodiscover_tasks(['backend'], related_name='tasks')

# 配置任务结果的过期时间
app.conf.result_expires = 3600  # 1小时

# 设置任务执行超时时间
app.conf.task_time_limit = 3600  # 1小时

# 设置任务软超时时间
app.conf.task_soft_time_limit = 3000  # 50分钟

# 配置任务路由
app.conf.task_routes = {
    'backend.tasks.build_kg_from_hadoop': {
        'queue': 'kg_build',
        'routing_key': 'kg.build'
    },
    'backend.tasks.process_hadoop_output': {
        'queue': 'kg_process',
        'routing_key': 'kg.process'
    }
}

# 设置工作池配置
app.conf.worker_pool_restarts = True
app.conf.worker_max_tasks_per_child = 100

# 配置日志
app.conf.worker_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
app.conf.worker_task_log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(task_id)s] %(message)s'

# 配置任务重试机制
app.conf.task_retry_backoff = 5  # 重试间隔5秒
app.conf.task_retry_backoff_max = 60  # 最大重试间隔60秒
app.conf.task_max_retries = 3  # 最大重试次数3次
