#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 配置文件
"""

# 消息代理配置 - 使用内存（本地测试用）
BROKER_URL = 'memory://localhost/'
BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,  # 任务过期时间（秒）
    'fanout_prefix': True,
    'fanout_patterns': True,
}

# 结果存储配置 - 使用内存（本地测试用）
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,
}

# 序列化配置
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# 时区配置
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_ENABLE_UTC = True

# 任务执行配置
CELERY_TASK_TIME_LIMIT = 3600  # 任务执行超时时间（秒）
CELERY_TASK_SOFT_TIME_LIMIT = 3000  # 任务软超时时间（秒）
CELERY_TASK_MAX_RETRIES = 3  # 任务最大重试次数

# 工作池配置
CELERY_WORKER_POOL = 'prefork'  # 工作池类型: prefork, eventlet, gevent, solo
CELERY_WORKER_CONCURRENCY = 4  # 并发工作进程数
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # 每个工作进程最多执行的任务数，超过后重启
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 每个工作进程预取的任务数

# 日志配置
CELERY_WORKER_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
CELERY_WORKER_TASK_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(task_id)s] %(message)s'
CELERY_WORKER_LOG_LEVEL = 'INFO'
CELERY_WORKER_REDIRECT_STDOUTS = True
CELERY_WORKER_REDIRECT_STDOUTS_LEVEL = 'INFO'

# 任务路由配置
CELERY_TASK_ROUTES = {
    'backend.tasks.build_kg_from_hadoop': {
        'queue': 'kg_build',
        'routing_key': 'kg.build'
    },
    'backend.tasks.process_hadoop_output': {
        'queue': 'kg_process',
        'routing_key': 'kg.process'
    }
}

# 任务队列配置
CELERY_QUEUES = {
    'default': {
        'exchange': 'default',
        'exchange_type': 'direct',
        'routing_key': 'default',
    },
    'kg_build': {
        'exchange': 'kg_build',
        'exchange_type': 'direct',
        'routing_key': 'kg.build',
    },
    'kg_process': {
        'exchange': 'kg_process',
        'exchange_type': 'direct',
        'routing_key': 'kg.process',
    },
}

# 任务过期时间
CELERY_TASK_RESULT_EXPIRES = 3600  # 1小时

# 禁用速率限制
CELERY_DISABLE_RATE_LIMITS = True

# 配置任务重试机制
CELERY_TASK_RETRY_BACKOFF = 5  # 重试间隔5秒
CELERY_TASK_RETRY_BACKOFF_MAX = 60  # 最大重试间隔60秒

# 启用任务跟踪
CELERY_TASK_TRACK_STARTED = True

# 启用远程控制
CELERY_ENABLE_REMOTE_CONTROL = True
