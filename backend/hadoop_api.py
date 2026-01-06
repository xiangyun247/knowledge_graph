"""

Hadoop �?Celery 集成 API

新增�?API 接口,用于支持批量处理�?Hadoop 集成

"""



import os

from fastapi import APIRouter, File, UploadFile, HTTPException, Form

from fastapi.responses import JSONResponse

from typing import List, Optional

from pydantic import BaseModel, Field

import uuid

import logging

from datetime import datetime



from backend.hadoop_service import get_hadoop_service

from backend.celery_service import get_celery_service



logger = logging.getLogger(__name__)



# 创建路由

router = APIRouter(prefix="/api/hadoop", tags=["Hadoop集成"])





class BatchUploadRequest(BaseModel):

    """批量上传请求"""

    file_ids: List[str] = Field(..., description="文件ID列表")





class BatchBuildRequest(BaseModel):

    """批量构建请求"""

    file_ids: List[str] = Field(..., description="文件ID列表")

    use_hadoop: bool = Field(True, description="是否使用Hadoop处理")





@router.post("/upload/batch")

async def batch_upload_files(files: List[UploadFile] = File(...)):

    """

    批量上传文件�?HDFS

    

    支持同时上传多个文件

    """

    try:

        # 导入 app 模块中的全局变量(延迟导入避免循环)

        import backend.app as app_module

        UPLOAD_DIR = app_module.UPLOAD_DIR

        uploaded_files = app_module.uploaded_files

        mysql_client = app_module.mysql_client

        

        uploaded_file_ids = []

        file_paths = []

        

        for file in files:

            # 生成文件ID

            file_id = str(uuid.uuid4())

            file_ext = os.path.splitext(file.filename)[1] if '.' in file.filename else ''

            local_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")

            

            # 保存到本�?

            content = b''

            with open(local_path, "wb") as f:

                while True:

                    chunk = await file.read(1024 * 1024)

                    if not chunk:

                        break

                    content += chunk

                    f.write(chunk)

            

            # 存储文件信息

            uploaded_files[file_id] = {

                "filename": file.filename,

                "path": local_path,

                "size": len(content),

                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            }

            

            uploaded_file_ids.append(file_id)

            file_paths.append({

                "file_id": file_id,

                "local_path": local_path,

                "filename": file.filename

            })

        

        # 上传�?HDFS

        hadoop_service = get_hadoop_service()

        upload_result = hadoop_service.upload_files_to_hdfs(file_paths)

        

        logger.info(f"批量上传完成: {len(files)} 个文�? HDFS上传成功: {upload_result['success_count']}")

        

        return {

            "status": "success",

            "total_files": len(files),

            "uploaded_file_ids": uploaded_file_ids,

            "hdfs_upload": upload_result,

            "message": f"成功上传 {len(files)} 个文�?其中 {upload_result['success_count']} 个已上传到HDFS"

        }

        

    except Exception as e:

        logger.error(f"批量上传失败: {e}")

        raise HTTPException(status_code=500, detail=f"批量上传失败: {str(e)}")





@router.post("/build/batch")

async def batch_build_kg(request: BatchBuildRequest):

    """

    批量构建知识图谱(使用Hadoop和Celery)- 异步方式

    

    流程:

    1. 立即返回任务ID

    2. 在后台线程中执行:

       - 上传文件到HDFS(如果还未上传)

       - 触发Hadoop MapReduce任务(PDF提取,清洗,分块)

       - 提交Celery任务处理文本�?

    """

    try:

        # 导入 app 模块中的全局变量(延迟导入避免循环)

        import backend.app as app_module

        uploaded_files = app_module.uploaded_files

        tasks = app_module.tasks

        TaskStatus = app_module.TaskStatus

        

        file_ids = request.file_ids

        use_hadoop = request.use_hadoop

        

        if not file_ids:

            raise HTTPException(status_code=400, detail="文件ID列表不能为空")

        

        # 生成任务ID

        task_id = str(uuid.uuid4())

        

        # 初始化任务信�?

        tasks[task_id] = {

            "status": TaskStatus.PROCESSING,

            "progress": 5,

            "current_chunk": 0,

            "total_chunks": 0,

            "entities_created": 0,

            "relations_created": 0,

            "message": "任务已创�?正在初始�?,

            "current_processing": "初始�?,

            "file_ids": file_ids,

            "use_hadoop": use_hadoop,

            "hadoop_result": None,

            "celery_task_id": None

        }

        

        if use_hadoop:

            # 在后台线程中执行 Hadoop 处理

            import threading

            

            def process_hadoop_background():

                """后台处理 Hadoop 任务"""

                try:

                    hadoop_service = get_hadoop_service()

                    

                    # 更新状�?

                    tasks[task_id]["progress"] = 10

                    tasks[task_id]["message"] = "开始上传文件到 HDFS"

                    tasks[task_id]["current_processing"] = "上传文件到HDFS"

                    

                    # 1. 确保文件已上传到 HDFS

                    file_paths = []

                    for file_id in file_ids:

                        if file_id not in uploaded_files:

                            logger.warning(f"文件不存�? {file_id}")

                            continue

                        

                        file_info = uploaded_files[file_id]

                        file_paths.append({

                            "file_id": file_id,

                            "local_path": file_info["path"],

                            "filename": file_info["filename"]

                        })

                    

                    # 上传�?HDFS

                    upload_result = hadoop_service.upload_files_to_hdfs(file_paths)

                    

                    # 检查上传结�?upload_files_to_hdfs 返回的是包含 success_count �?failed_count 的字�?

                    if upload_result.get("failed_count", 0) > 0:

                        error_msg = f"部分文件上传失败: {upload_result.get('failed_count', 0)} 个文件失�?

                        if upload_result.get("failed_files"):

                            error_details = ", ".join([f.get("filename", "未知文件") for f in upload_result["failed_files"]])

                            error_msg += f" ({error_details})"

                        tasks[task_id]["status"] = TaskStatus.FAILED

                        tasks[task_id]["message"] = error_msg

                        logger.error(f"任务 {task_id} 文件上传失败: {error_msg}")

                        return

                    

                    if upload_result.get("success_count", 0) == 0:

                        tasks[task_id]["status"] = TaskStatus.FAILED

                        tasks[task_id]["message"] = "所有文件上传到HDFS失败"

                        logger.error(f"任务 {task_id} 所有文件上传失�?)

                        return

                    

                    # 更新状�?

                    tasks[task_id]["progress"] = 20

                    tasks[task_id]["message"] = "文件上传完成,开�?Hadoop 处理"

                    tasks[task_id]["current_processing"] = "Hadoop MapReduce处理"

                    

                    # 2. 触发 Hadoop MapReduce 任务

                    hadoop_result = hadoop_service.process_files_with_hadoop(file_ids)

                    tasks[task_id]["hadoop_result"] = hadoop_result

                    

                    # 3. 提交 Celery 任务

                    if hadoop_result.get("success") and hadoop_result.get("final_output"):

                        tasks[task_id]["progress"] = 50

                        tasks[task_id]["message"] = "Hadoop处理完成,提交Celery任务"

                        tasks[task_id]["current_processing"] = "提交Celery任务"

                        

                        celery_service = get_celery_service()

                        celery_result = celery_service.submit_chunk_processing_task(

                            hdfs_path=hadoop_result["final_output"],

                            file_id=file_ids[0],  # 使用第一个文件ID作为标识

                            task_id=task_id

                        )

                        

                        tasks[task_id]["celery_task_id"] = celery_result.get("celery_task_id")

                        tasks[task_id]["progress"] = 60

                        tasks[task_id]["message"] = "Celery任务已提�?正在处理文本�?

                        tasks[task_id]["current_processing"] = "Celery处理�?

                    else:

                        tasks[task_id]["status"] = TaskStatus.FAILED

                        tasks[task_id]["message"] = f"Hadoop处理失败: {hadoop_result.get('error', '未知错误')}"

                        tasks[task_id]["progress"] = 100

                except Exception as e:

                    logger.error(f"后台处理 Hadoop 任务失败: {e}", exc_info=True)

                    tasks[task_id]["status"] = TaskStatus.FAILED

                    tasks[task_id]["message"] = f"处理失败: {str(e)}"

                    tasks[task_id]["progress"] = 100

            

            # 启动后台线程

            thread = threading.Thread(target=process_hadoop_background, daemon=True)

            thread.start()

            

            # 立即返回任务ID

            return {

                "status": "success",

                "task_id": task_id,

                "message": "批量构建任务已启�?请通过 /api/hadoop/task/{task_id}/status 查询进度"

            }

        else:

            # 不使�?Hadoop,使用原有方式(单个文件处理)

            tasks[task_id]["status"] = TaskStatus.FAILED

            tasks[task_id]["message"] = "未使用Hadoop模式,请使用原有接�?

            return {

                "status": "error",

                "task_id": task_id,

                "error": "请使用原有接口处理单个文�?或设置use_hadoop=true"

            }

        

    except Exception as e:

        logger.error(f"批量构建知识图谱失败: {e}")

        raise HTTPException(status_code=500, detail=f"批量构建失败: {str(e)}")





@router.get("/task/{task_id}/status")

async def get_hadoop_task_status(task_id: str):

    """

    获取 Hadoop + Celery 任务状�?

    

    合并查询 Hadoop �?Celery 任务状�?

    """

    try:

        # 导入 app 模块中的全局变量(延迟导入避免循环)

        import backend.app as app_module

        tasks = app_module.tasks

        TaskStatus = app_module.TaskStatus

        

        # 从内存任务中获取信息

        task_info = tasks.get(task_id, {})

        

        # 如果任务中有 Celery 任务ID,查询 Celery 状�?

        celery_task_id = task_info.get("celery_task_id")

        celery_status = None

        

        if celery_task_id:

            celery_service = get_celery_service()

            celery_status = celery_service.get_task_status(celery_task_id)

        

        # 合并状�?

        result = {

            "task_id": task_id,

            "status": task_info.get("status", "unknown"),

            "progress": task_info.get("progress", 0),

            "message": task_info.get("message", ""),

            "current_processing": task_info.get("current_processing", ""),

            "hadoop_status": "completed" if task_info.get("use_hadoop") else "not_used",

            "celery_status": celery_status

        }

        

        return {

            "status": "success",

            "data": result

        }

        

    except Exception as e:

        logger.error(f"获取任务状态失�? {task_id}, 错误: {e}")

        raise HTTPException(status_code=500, detail=f"获取任务状态失�? {str(e)}")
