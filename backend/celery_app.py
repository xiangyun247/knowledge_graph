#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 应用配置
"""

from celery import Celery
import os
import logging

logger = logging.getLogger(__name__)

# Redis 连接配置
redis_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

# 创建 Celery 应用
celery_app = Celery(
    "knowledge_graph",
    broker=redis_url,
    backend=redis_url,
    include=["backend.celery_tasks"]
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟
    task_soft_time_limit=25 * 60,  # 25分钟
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

logger.info(f"Celery 应用初始化完成,Redis: {redis_url}")

