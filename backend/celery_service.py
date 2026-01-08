#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 服务封装
"""

import logging
from typing import List, Dict, Any, Optional
from celery.result import AsyncResult

# 全局 Celery 服务实例
_celery_service_instance = None

logger = logging.getLogger(__name__)


class CeleryService:
    """Celery 服务类"""
    
    def __init__(self):
        self.celery_app = None
        self._initialize_celery()
    
    def _initialize_celery(self):
        """初始化 Celery 应用"""
        try:
            # 导入 Celery 应用
            from backend.celery_app import app
            self.celery_app = app
            logger.info("Celery 服务初始化成功")
        except Exception as e:
            logger.error(f"Celery 服务初始化失败: {e}", exc_info=True)
            self.celery_app = None
    
    def is_available(self) -> bool:
        """
        检查 Celery 服务是否可用
        
        Returns:
            bool: Celery 服务是否可用
        """
        return self.celery_app is not None
    
    def submit_task(self, task_name: str, *args, **kwargs) -> Optional[str]:
        """
        提交 Celery 任务
        
        Args:
            task_name: 任务名称
            *args: 任务参数
            **kwargs: 任务关键字参数
            
        Returns:
            Optional[str]: 任务ID，如果提交失败返回None
        """
        if not self.is_available():
            logger.error("Celery 服务不可用，无法提交任务")
            return None
        
        try:
            # 获取任务对象
            task = self.celery_app.send_task(task_name, args=args, kwargs=kwargs)
            logger.info(f"任务提交成功, task_id={task.id}, task_name={task_name}")
            return task.id
        except Exception as e:
            logger.error(f"提交任务失败, task_name={task_name}, error={e}", exc_info=True)
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息
        """
        if not self.is_available():
            return {
                "status": "ERROR",
                "message": "Celery 服务不可用"
            }
        
        try:
            result = AsyncResult(task_id, app=self.celery_app)
            
            status = result.status
            result_data = None
            error = None
            
            if result.ready():
                if result.successful():
                    result_data = result.result
                else:
                    error = str(result.result) if result.result else "未知错误"
            
            return {
                "task_id": task_id,
                "status": status,
                "result": result_data,
                "error": error,
                "traceback": result.traceback if hasattr(result, 'traceback') else None
            }
        except Exception as e:
            logger.error(f"获取任务状态失败, task_id={task_id}, error={e}", exc_info=True)
            return {
                "task_id": task_id,
                "status": "ERROR",
                "message": str(e)
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否取消成功
        """
        if not self.is_available():
            logger.error("Celery 服务不可用，无法取消任务")
            return False
        
        try:
            result = AsyncResult(task_id, app=self.celery_app)
            result.revoke(terminate=True)
            logger.info(f"任务取消成功, task_id={task_id}")
            return True
        except Exception as e:
            logger.error(f"取消任务失败, task_id={task_id}, error={e}", exc_info=True)
            return False
    
    def build_kg_from_hadoop(self, task_id: str, file_ids: List[str], hadoop_result: Dict[str, Any]) -> Optional[str]:
        """
        从 Hadoop 结果构建知识图谱
        
        Args:
            task_id: 任务ID
            file_ids: 文件ID列表
            hadoop_result: Hadoop处理结果
            
        Returns:
            Optional[str]: Celery任务ID，如果提交失败返回None
        """
        return self.submit_task(
            "backend.tasks.build_kg_from_hadoop",
            task_id=task_id,
            file_ids=file_ids,
            hadoop_result=hadoop_result
        )
    
    def process_hadoop_output(self, output_path: str) -> Optional[str]:
        """
        处理 Hadoop 输出
        
        Args:
            output_path: Hadoop输出路径
            
        Returns:
            Optional[str]: Celery任务ID，如果提交失败返回None
        """
        return self.submit_task(
            "backend.tasks.process_hadoop_output",
            output_path=output_path
        )
    
    def cleanup_resources(self, task_id: str) -> Optional[str]:
        """
        清理资源
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[str]: Celery任务ID，如果提交失败返回None
        """
        return self.submit_task(
            "backend.tasks.cleanup_resources",
            task_id=task_id
        )


def get_celery_service() -> CeleryService:
    """
    获取 Celery 服务实例(单例模式)
    
    Returns:
        CeleryService: Celery服务实例
    """
    global _celery_service_instance
    
    if _celery_service_instance is None:
        _celery_service_instance = CeleryService()
    
    return _celery_service_instance
