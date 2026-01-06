#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 服务封装
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 全局 Celery 服务实例
_celery_service_instance = None


class CeleryService:
    """Celery 服务类"""
    
    def __init__(self):
        try:
            from backend.celery_app import celery_app
            from backend.celery_tasks import download_and_process_chunks
            self.celery_app = celery_app
            self.download_and_process_chunks = download_and_process_chunks
            logger.info("Celery 服务初始化成功")
        except Exception as e:
            logger.error(f"Celery 服务初始化失败: {e}")
            self.celery_app = None
            self.download_and_process_chunks = None
    
    def submit_chunk_processing_task(
        self,
        hdfs_path: str,
        file_id: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        提交文本块处理任务
        
        Args:
            hdfs_path: HDFS 中的文本块目录路径
            file_id: 文件 ID
            task_id: 任务 ID
            
        Returns:
            任务提交结果
        """
        if not self.download_and_process_chunks:
            raise Exception("Celery 任务未初始化")
        
        try:
            # 提交任务
            result = self.download_and_process_chunks.delay(
                hdfs_path=hdfs_path,
                file_id=file_id,
                task_id=task_id
            )
            
            logger.info(f"Celery 任务已提交: {result.id} (HDFS路径: {hdfs_path})")
            
            return {
                "success": True,
                "celery_task_id": result.id,
                "message": "任务已提交"
            }
        except Exception as e:
            logger.error(f"提交 Celery 任务失败: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: Celery 任务 ID
            
        Returns:
            任务状态信息
        """
        if not self.celery_app:
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": "Celery 应用未初始化"
            }
        
        try:
            from celery.result import AsyncResult
            
            result = AsyncResult(task_id, app=self.celery_app)
            
            return {
                "task_id": task_id,
                "status": result.status,
                "ready": result.ready(),
                "successful": result.successful() if result.ready() else None,
                "failed": result.failed() if result.ready() else None,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
            }
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": str(e),
            }


def get_celery_service() -> CeleryService:
    """
    获取 Celery 服务实例(单例模式)
    
    Returns:
        CeleryService 实例
    """
    global _celery_service_instance
    
    if _celery_service_instance is None:
        _celery_service_instance = CeleryService()
    
    return _celery_service_instance

