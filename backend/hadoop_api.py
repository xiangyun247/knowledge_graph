#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hadoop 与 Celery 集成 API

说明:
- 提供批量上传 PDF 到 HDFS 的接口
- 提供批量触发 Hadoop + Celery 构建知识图谱的接口
- 提供查询批量任务状态的接口

注意:
- 为避免循环导入, 与 FastAPI 应用相关的全局变量(如 uploaded_files、tasks、TaskStatus)
  通过在函数内部延迟导入 `backend.app` 获取
"""

import os
import uuid
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.hadoop_service import get_hadoop_service
# 暂时移除 Celery 导入，避免模块加载时触发异常
# from backend.celery_service import get_celery_service

logger = logging.getLogger(__name__)


# 创建路由
router = APIRouter(prefix="/api/hadoop", tags=["Hadoop集成"])


class BatchBuildRequest(BaseModel):
    """批量构建知识图谱请求体"""

    file_ids: List[str] = Field(..., description="要处理的文件ID列表")
    use_hadoop: bool = Field(True, description="是否使用 Hadoop 进行批量处理")


def _get_app_globals() -> Dict[str, Any]:
    """
    延迟导入 backend.app, 避免循环依赖

    Returns:
        包含 UPLOAD_DIR、uploaded_files、tasks、TaskStatus、mysql_client 等的字典
    """
    import backend.app as app_module

    return {
        "UPLOAD_DIR": app_module.UPLOAD_DIR,
        "uploaded_files": app_module.uploaded_files,
        "tasks": app_module.tasks,
        "TaskStatus": app_module.TaskStatus,
        "mysql_client": getattr(app_module, "mysql_client", None),
        "history_records": getattr(app_module, "history_records", None),
    }


@router.post("/upload/batch")
async def batch_upload_files(files: List[UploadFile] = File(...)):
    """
    批量上传 PDF 文件到本地并同步上传到 HDFS

    - 将上传的文件保存到 backend/uploads 目录
    - 记录到 `backend.app.uploaded_files`
    - 调用 `HadoopService.upload_files_to_hdfs` 上传到 HDFS
    """
    if not files:
        raise HTTPException(status_code=400, detail="文件列表不能为空")

    try:
        globals_ = _get_app_globals()
        UPLOAD_DIR = globals_["UPLOAD_DIR"]
        uploaded_files = globals_["uploaded_files"]
        mysql_client = globals_["mysql_client"]

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        uploaded_file_ids: List[str] = []
        file_paths: List[Dict[str, str]] = []

        for file in files:
            # 生成文件ID
            file_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1] if "." in file.filename else ""
            local_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")

            # 保存到本地
            size = 0
            with open(local_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)

            # 记录到内存
            uploaded_files[file_id] = {
                "filename": file.filename,
                "path": local_path,
                "size": size,
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            uploaded_file_ids.append(file_id)
            file_paths.append(
                {
                    "file_id": file_id,
                    "local_path": local_path,
                    "filename": file.filename,
                }
            )

        # 调用 Hadoop 服务, 上传到 HDFS
        hadoop_service = get_hadoop_service()
        upload_result = hadoop_service.upload_files_to_hdfs(file_paths)

        logger.info(
            "批量上传完成: %d 个文件, HDFS 上传成功: %d, 失败: %d",
            len(files),
            upload_result.get("success_count", 0),
            upload_result.get("failed_count", 0),
        )

        # 可选: 写入上传历史到 MySQL
        if mysql_client:
            try:
                for fid in uploaded_file_ids:
                    info = uploaded_files.get(fid, {})
                    mysql_client.create_history_record(
                        file_id=fid,
                        file_name=info.get("filename", ""),
                        file_type="hadoop_upload",
                        task_id=fid,
                    )
            except Exception as e:  # pragma: no cover - 日志用途
                logger.error("保存批量上传历史记录到 MySQL 失败: %s", e)

        return JSONResponse(
            {
                "status": "success",
                "total_files": len(files),
                "uploaded_file_ids": uploaded_file_ids,
                "hdfs_upload": upload_result,
                "message": "批量上传完成",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("批量上传失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量上传失败: {e}")


def _run_hadoop_and_celery_in_background(task_id: str, file_ids: List[str], use_hadoop: bool) -> None:
    """
    在后台线程中执行 Hadoop 处理
    
    注意：当前版本仅执行 Hadoop 处理，不包含 Celery 任务
    """
    from backend.hadoop_service import get_hadoop_service  # 局部导入避免循环

    globals_ = _get_app_globals()
    tasks = globals_["tasks"]
    TaskStatus = globals_["TaskStatus"]

    try:
        if task_id not in tasks:
            logger.warning("任务不存在: %s", task_id)
            return

        if not use_hadoop:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = "当前仅支持 use_hadoop=True"
            tasks[task_id]["progress"] = 100
            return

        tasks[task_id]["message"] = "正在执行 Hadoop 处理"
        tasks[task_id]["progress"] = 10

        hadoop_service = get_hadoop_service()
        hadoop_result = hadoop_service.process_files_with_hadoop(file_ids)
        tasks[task_id]["hadoop_result"] = hadoop_result

        if not hadoop_result.get("success"):
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = f"Hadoop 处理失败: {hadoop_result.get('error')}"
            tasks[task_id]["progress"] = 100
            return

        # Hadoop 处理成功，标记为完成
        final_output = hadoop_result.get("final_output")
        if not final_output:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = "Hadoop 处理未返回有效的输出路径"
            tasks[task_id]["progress"] = 100
            return

        tasks[task_id]["status"] = TaskStatus.COMPLETED
        tasks[task_id]["message"] = "Hadoop 处理完成"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["current_processing"] = "完成"
        tasks[task_id]["hadoop_result"] = hadoop_result
        logger.info(f"任务 {task_id} 完成: Hadoop 处理成功，输出路径: {final_output}")

    except Exception as e:
        # 捕获所有异常，记录日志，并将任务标记为失败
        logger.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
        if task_id in tasks:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = f"后台任务执行失败: {e}"
            tasks[task_id]["progress"] = 100


@router.post("/build/batch")
async def batch_build_kg(request: BatchBuildRequest):
    """
    批量触发 Hadoop + Celery 构建知识图谱 (异步任务)

    步骤:
    1. 创建任务ID, 在内存中初始化任务状态
    2. 启动后台线程:
       - 使用 Hadoop 进行 PDF 提取 / 文本清洗 / 文本分块
       - 使用 Celery 从 HDFS 下载文本块并构建知识图谱
    3. 立即返回 task_id, 前端通过 /status 接口轮询任务状态
    """
    globals_ = _get_app_globals()
    uploaded_files = globals_["uploaded_files"]
    tasks = globals_["tasks"]
    TaskStatus = globals_["TaskStatus"]

    file_ids = request.file_ids or []
    if not file_ids:
        raise HTTPException(status_code=400, detail="文件ID列表不能为空")

    # 校验文件是否存在
    missing = [fid for fid in file_ids if fid not in uploaded_files]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"以下文件ID不存在或尚未上传: {', '.join(missing)}",
        )

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 初始化任务信息
    tasks[task_id] = {
        "status": TaskStatus.PROCESSING,
        "progress": 5,
        "current_chunk": 0,
        "total_chunks": 0,
        "entities_created": 0,
        "relations_created": 0,
        "message": "任务已创建,正在初始化",
        "current_processing": "初始化",
        "file_ids": file_ids,
        "use_hadoop": request.use_hadoop,
        "hadoop_result": None,
        "celery_task_id": None,
    }

    # 启动后台线程执行实际任务
    thread = threading.Thread(
        target=_run_hadoop_and_celery_in_background,
        args=(task_id, file_ids, request.use_hadoop),
        daemon=True,
    )
    thread.start()

    return JSONResponse(
        {
            "status": "accepted",
            "task_id": task_id,
            "message": "批量构建任务已创建,正在后台执行",
        }
    )


@router.get("/status/{task_id}")
async def get_batch_task_status(task_id: str):
    """
    查询批量构建任务状态

    返回内容:
    - 基础任务信息(来自 backend.app.tasks)
    - 如果存在 Celery 任务, 额外返回 celery_status
    """
    globals_ = _get_app_globals()
    tasks = globals_["tasks"]

    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    response: Dict[str, Any] = {"task_id": task_id, "task": task}

    # 暂时禁用 Celery 状态查询
    # celery_task_id = task.get("celery_task_id")
    # if celery_task_id:
    #     try:
    #         from backend.celery_service import get_celery_service
    #         celery_service = get_celery_service()
    #         celery_status = celery_service.get_task_status(celery_task_id)
    #         response["celery_status"] = celery_status
    #     except Exception as e:  # pragma: no cover - 日志用途
    #         logger.error("获取 Celery 任务状态失败: %s", e)
    #         response["celery_status_error"] = str(e)

    return JSONResponse(response)


@router.get("/tasks")
async def list_batch_tasks():
    """
    简要列出所有 Hadoop 批量任务
    """
    globals_ = _get_app_globals()
    tasks = globals_["tasks"]

    summary = []
    for task_id, info in tasks.items():
        summary.append(
            {
                "task_id": task_id,
                "status": info.get("status"),
                "progress": info.get("progress"),
                "message": info.get("message"),
                "file_ids": info.get("file_ids"),
            }
        )

    return JSONResponse({"tasks": summary})



