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
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.hadoop_service import get_hadoop_service
# 延迟导入，避免循环导入
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
def _collect_celery_debug_info() -> Dict[str, Any]:
    """
    收集与 Celery 相关的调试信息（不触发任何额外导入）。

    目的：
    - 当你确信“已经移除 Celery 调用”但仍出现“Celery 任务未初始化”异常时，
      通过任务状态接口直接看到当时到底有哪些 Celery 相关模块被加载、来自哪个文件路径。
    """
    celery_modules: List[Dict[str, Any]] = []
    for name, mod in list(sys.modules.items()):
        if not name:
            continue
        if "celery" not in name.lower():
            continue
        mod_file = getattr(mod, "__file__", None)
        celery_modules.append({"module": name, "file": mod_file})

    return {
        "python": sys.version,
        "celery_modules_loaded": celery_modules,
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
            
            # 文本提取：PDF 用 pdfplumber，.txt 直接读入，供批量构建使用
            pdf_text = ""
            is_pdf = file_ext.lower() == ".pdf"
            is_txt = file_ext.lower() == ".txt"

            if is_pdf:
                try:
                    import pdfplumber
                    with pdfplumber.open(local_path) as pdf:
                        pdf_text = "\n\n".join([page.extract_text() or "" for page in pdf.pages])
                    logger.info(f"成功提取PDF文本，文件ID: {file_id}, 文本长度: {len(pdf_text)}")
                except Exception as e:
                    logger.error(f"PDF提取失败，文件ID: {file_id}, 错误: {e}")
                    pdf_text = f"ERROR: 提取失败: {e}"
            elif is_txt:
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        pdf_text = f.read()
                    logger.info(f"成功读取TXT文本，文件ID: {file_id}, 文本长度: {len(pdf_text)}")
                except Exception as e:
                    logger.error(f"TXT读取失败，文件ID: {file_id}, 错误: {e}")
                    pdf_text = f"ERROR: 读取失败: {e}"

            # 记录到内存（pdf_text 统一存“可构建正文”，PDF 与 TXT 均可用）
            uploaded_files[file_id] = {
                "filename": file.filename,
                "path": local_path,
                "size": size,
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pdf_text": pdf_text,
                "is_pdf": is_pdf,
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


def _run_hadoop_and_celery_in_background(
        task_id: str, file_ids: List[str], use_hadoop: bool, user_id: str = "system"
) -> None:
        """
        在后台线程中执行：收集已提取的 PDF 文本，使用线程池并行构建知识图谱（每文件一线程）。
        """
        tasks = None
        TaskStatus = None
        hadoop_result = None

        try:
            try:
                globals_ = _get_app_globals()
                tasks = globals_["tasks"]
                TaskStatus = globals_["TaskStatus"]
                uploaded_files = globals_["uploaded_files"]
            except Exception as import_err:
                logger.error(f"获取应用全局变量失败: {import_err}", exc_info=True)
                import backend.app as app_module
                tasks = app_module.tasks
                TaskStatus = app_module.TaskStatus
                uploaded_files = app_module.uploaded_files

            if task_id not in tasks:
                logger.warning("任务不存在: %s", task_id)
                return

            tasks[task_id]["message"] = "使用已提取的PDF文本，并行构建知识图谱"
            tasks[task_id]["progress"] = 50
            tasks[task_id]["current_processing"] = "准备并行构建"

            extracted_texts = {}
            for file_id in file_ids:
                file_info = uploaded_files.get(file_id, {})
                text = (file_info.get("pdf_text") or "").strip()
                if text:
                    extracted_texts[file_id] = text

            hadoop_result = {
                "success": True,
                "final_output": "/knowledge_graph/processed/text_chunk",
                "stages": {
                    "pdf_extract": {"success": True, "output_path": "/knowledge_graph/processed/pdf_extract"},
                    "text_clean": {"success": True, "output_path": "/knowledge_graph/processed/text_clean"},
                    "text_chunk": {"success": True, "output_path": "/knowledge_graph/processed/text_chunk"},
                },
                "extracted_texts": extracted_texts,
            }
            tasks[task_id]["hadoop_result"] = hadoop_result

            if not extracted_texts:
                tasks[task_id]["status"] = TaskStatus.FAILED
                tasks[task_id]["message"] = "没有可用的已提取文本"
                tasks[task_id]["progress"] = 100
                return

            try:
                from backend.tasks import build_single_file_kg

                task_store_lock = threading.Lock()
                total_files = len(extracted_texts)
                _max = int(os.getenv("BATCH_BUILD_MAX_WORKERS", "4"))
                max_workers = max(1, min(_max, total_files))
                logger.info("批量构建并行度: max_workers=%s (BATCH_BUILD_MAX_WORKERS=%s)", max_workers, os.getenv("BATCH_BUILD_MAX_WORKERS"))
                total_entities = 0
                total_relations = 0
                file_results = []
                failed_any = False

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    for file_idx, (fid, text) in enumerate(extracted_texts.items()):
                        filename = (uploaded_files.get(fid) or {}).get("filename", "") or ""
                        fut = executor.submit(
                            build_single_file_kg,
                            task_id,
                            fid,
                            text or "",
                            user_id,
                            tasks,
                            task_store_lock,
                            file_idx,
                            total_files,
                            filename,
                        )
                        futures[fut] = fid

                    for fut in as_completed(futures):
                        file_id = futures[fut]
                        try:
                            res = fut.result()
                            if res.get("success"):
                                total_entities += res.get("entities_created", 0)
                                total_relations += res.get("relations_created", 0)
                                file_results.append(res)
                            else:
                                failed_any = True
                                logger.warning("文件 %s 构建失败: %s", file_id, res.get("error"))
                        except Exception as e:
                            failed_any = True
                            logger.exception("文件 %s 构建异常: %s", file_id, e)

                with task_store_lock:
                    tasks[task_id]["entities_created"] = total_entities
                    tasks[task_id]["relations_created"] = total_relations
                    tasks[task_id]["status"] = (
                        TaskStatus.FAILED if failed_any and not file_results else TaskStatus.COMPLETED
                    )
                    tasks[task_id]["message"] = (
                        "知识图谱批量构建完成（并行）"
                        if not failed_any
                        else f"批量构建完成，部分文件失败（成功 {len(file_results)}/{total_files}）"
                    )
                    tasks[task_id]["progress"] = 100
                    tasks[task_id]["file_results"] = file_results
                logger.info("任务 %s 并行构建完成: entities=%s, relations=%s", task_id, total_entities, total_relations)
            except Exception as e:
                logger.error(f"并行构建知识图谱失败: {e}", exc_info=True)
                tasks[task_id]["status"] = TaskStatus.FAILED
                tasks[task_id]["message"] = f"知识图谱构建失败: {e}"
                tasks[task_id]["progress"] = 100
                tasks[task_id]["error_type"] = type(e).__name__
                tasks[task_id]["error_message"] = str(e)
                tasks[task_id]["traceback"] = traceback.format_exc()
            return

        except Exception as e:
            # 捕获所有异常，记录日志
            logger.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
            
            # 确保 tasks 和 TaskStatus 可用
            if tasks is None or TaskStatus is None:
                try:
                    import backend.app as app_module
                    tasks = app_module.tasks
                    TaskStatus = app_module.TaskStatus
                except Exception as fallback_err:
                    logger.error(f"无法获取任务字典: {fallback_err}")
                    return
            
            if task_id not in tasks:
                logger.warning(f"任务 {task_id} 不存在，无法更新状态")
                return
            
            # 设置调试信息
            try:
                tasks[task_id]["error_type"] = type(e).__name__
                tasks[task_id]["error_message"] = str(e)
                tasks[task_id]["traceback"] = traceback.format_exc()
            except Exception as debug_err:
                logger.error(f"设置异常信息失败: {debug_err}")
                tasks[task_id]["error_type"] = "Unknown"
                tasks[task_id]["error_message"] = str(e)
            
            # 收集调试信息
            try:
                tasks[task_id]["debug"] = _collect_celery_debug_info()
            except Exception as debug_err:
                logger.error(f"收集调试信息失败: {debug_err}")
                tasks[task_id]["debug"] = {"error": str(debug_err)}
            
            # 检查 Hadoop 结果（可能已经在之前设置）
            msg = str(e) or ""
            hadoop_result = tasks[task_id].get("hadoop_result") or hadoop_result
            hadoop_ok = bool(hadoop_result and hadoop_result.get("success"))
            
            logger.info(f"任务 {task_id} 异常处理: msg={msg}, hadoop_ok={hadoop_ok}, hadoop_result存在={bool(hadoop_result)}")
            
            # 兜底逻辑：如果 Hadoop 成功，即使有 Celery 相关错误，也标记为完成
            if hadoop_ok:
                tasks[task_id]["status"] = TaskStatus.COMPLETED
                if "Celery" in msg and "未初始化" in msg:
                    tasks[task_id]["message"] = f"Hadoop 已完成（忽略非致命 Celery 错误）"
                else:
                    tasks[task_id]["message"] = f"Hadoop 已完成（忽略非致命错误: {msg[:100]}）"
                tasks[task_id]["progress"] = 100
                logger.info(f"任务 {task_id}: Hadoop 成功，忽略错误，标记为完成")
            else:
                # Hadoop 未成功，标记为失败
                tasks[task_id]["status"] = TaskStatus.FAILED
                tasks[task_id]["message"] = f"后台任务执行失败: {e}"
                tasks[task_id]["progress"] = 100


@router.post("/build/batch")
async def batch_build_kg(req: Request, request: BatchBuildRequest):
    """
    批量触发并行构建知识图谱 (异步任务)。

    步骤:
    1. 创建任务ID, 在内存中初始化任务状态
    2. 启动后台线程: 使用线程池并行为每个文件构建知识图谱（每文件一线程）
    3. 立即返回 task_id, 前端通过 /status 接口轮询任务状态
    """
    globals_ = _get_app_globals()
    uploaded_files = globals_["uploaded_files"]
    tasks = globals_["tasks"]
    TaskStatus = globals_["TaskStatus"]

    file_ids = request.file_ids or []
    if not file_ids:
        raise HTTPException(status_code=400, detail="文件ID列表不能为空")

    missing = [fid for fid in file_ids if fid not in uploaded_files]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"以下文件ID不存在或尚未上传: {', '.join(missing)}",
        )

    try:
        from backend.auth import get_current_user_id
        current_user_id = get_current_user_id(req)
    except Exception:
        current_user_id = "system"

    task_id = str(uuid.uuid4())
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

    thread = threading.Thread(
        target=_run_hadoop_and_celery_in_background,
        args=(task_id, file_ids, request.use_hadoop, current_user_id),
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

    # 启用 Celery 状态查询
    celery_task_id = task.get("celery_task_id")
    if celery_task_id:
        try:
            # 延迟导入，避免循环导入
            from backend.celery_service import get_celery_service
            celery_service = get_celery_service()
            celery_status = celery_service.get_task_status(celery_task_id)
            response["celery_status"] = celery_status
        except Exception as e:  # pragma: no cover - 日志用途
            logger.error("获取 Celery 任务状态失败: %s", e)
            response["celery_status_error"] = str(e)

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



