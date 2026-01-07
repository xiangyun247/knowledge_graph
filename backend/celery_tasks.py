"""

Celery 任务定义

用于异步处理知识图谱构建任务

"""



import os

import sys

import logging

from typing import Dict, Any, Optional

from pathlib import Path



# 添加项目根目录到 Python 路径

project_root = Path(__file__).parent.parent

sys.path.insert(0, str(project_root))



try:

    from backend.celery_app import celery_app

except ImportError:

    # 如果在项目根目录运行,可能需要调整导入路�?

    sys.path.insert(0, str(project_root.parent) if project_root.parent.exists() else str(project_root))

    from backend.celery_app import celery_app



# 配置日志

logging.basicConfig(

    level=logging.INFO,

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'

)

logger = logging.getLogger(__name__)



try:

    from hadoop.utils.hdfs_client import HDFSClient

except ImportError:

    HDFSClient = None

    logger.warning("HDFSClient 导入失败,HDFS 功能将不可用")



# 全局变量(延迟初始�?

neo4j_client = None

llm_client = None

embedding_client = None

kg_builder = None





def get_kg_builder():

    """获取知识图谱构建器实�?单例模式)"""

    global neo4j_client, llm_client, embedding_client, kg_builder

    

    if kg_builder is None:

        try:

            from db.neo4j_client import Neo4jClient

            from llm.client import LLMClient, EmbeddingClient

            from kg.builder import KnowledgeGraphBuilder

            

            # 初始化客户端

            neo4j_client = Neo4jClient()

            llm_client = LLMClient()

            embedding_client = EmbeddingClient()

            

            # 创建知识图谱构建�?

            kg_builder = KnowledgeGraphBuilder(

                neo4j_client=neo4j_client,

                llm_client=llm_client

            )

            

            logger.info("知识图谱构建器初始化成功")

        except Exception as e:

            logger.error(f"知识图谱构建器初始化失败: {e}")

            raise

    

    return kg_builder





@celery_app.task(bind=True, name="backend.celery_tasks.process_text_chunk")

def process_text_chunk(

    self,

    chunk_text: str,

    chunk_id: str,

    file_id: str,

    task_id: str

    ) -> Dict[str, Any]:

    """

    处理文本�?使用 LLM 提取实体和关�?

    

    Args:

        chunk_text: 文本块内�?

        chunk_id: 文本�?ID

        file_id: 文件 ID

        task_id: 任务 ID

        

    Returns:

        处理结果

    """

    try:

        logger.info(f"开始处理文本块: {chunk_id} (任务: {task_id})")

        

        # 获取知识图谱构建�?

        builder = get_kg_builder()

        

        # 处理文本�?

        result = builder.process_text(chunk_text)

        

        logger.info(

            f"文本块处理完�? {chunk_id}, "

            f"实体�?{result.get('entities_created', 0)}, "

            f"关系�?{result.get('relations_created', 0)}"

        )

        

        return {

            "success": True,

            "chunk_id": chunk_id,

            "file_id": file_id,

            "task_id": task_id,

            "entities_created": result.get("entities_created", 0),

            "relations_created": result.get("relations_created", 0),

            "sentences_processed": result.get("sentences_processed", 0),

        }

        

    except Exception as e:

        logger.error(f"处理文本块失�? {chunk_id}, 错误: {e}")

        # 重试任务

        raise self.retry(exc=e, countdown=60, max_retries=3)





@celery_app.task(bind=True, name="backend.celery_tasks.build_knowledge_graph")

def build_knowledge_graph(

    self,

    file_id: str,

    task_id: str,

    chunks: list

) -> Dict[str, Any]:

    """

    构建知识图谱(协调任务)

    

    Args:

        file_id: 文件 ID

        task_id: 任务 ID

        chunks: 文本块列�?[{"chunk_id": str, "text": str}, ...]

        

    Returns:

        构建结果

    """

    try:

        logger.info(f"开始构建知识图�? {file_id} (任务: {task_id})")

        

        # 提交所有文本块处理任务

        tasks = []

        for chunk in chunks:

            chunk_id = chunk.get("chunk_id")

            chunk_text = chunk.get("text")

            

            if not chunk_id or not chunk_text:

                continue

            

            # 提交任务

            task = process_text_chunk.delay(

                chunk_text=chunk_text,

                chunk_id=chunk_id,

                file_id=file_id,

                task_id=task_id

            )

            tasks.append(task)

        

        logger.info(f"已提�?{len(tasks)} 个文本块处理任务")

        

        # 等待所有任务完�?可�?根据需求决定是否等�?

        # results = [task.get() for task in tasks]

        

        return {

            "success": True,

            "file_id": file_id,

            "task_id": task_id,

            "chunks_count": len(chunks),

            "tasks_submitted": len(tasks),

        }

        

    except Exception as e:

        logger.error(f"构建知识图谱失败: {file_id}, 错误: {e}")

        raise self.retry(exc=e, countdown=60, max_retries=3)





@celery_app.task(bind=True, name="backend.celery_tasks.download_and_process_chunks")

def download_and_process_chunks(

    self,

    hdfs_path: str,

    file_id: str,

    task_id: str

) -> Dict[str, Any]:

    """

    �?HDFS 下载文本块并处理

    

    Args:

        hdfs_path: HDFS 中的文本块目录路�?

        file_id: 文件 ID

        task_id: 任务 ID

        

    Returns:

        处理结果

    """

    try:

        logger.info(f"开始从 HDFS 下载文本�? {hdfs_path}")

        

        # 创建 HDFS 客户�?

        hdfs_host = os.getenv("HADOOP_NAMENODE", "localhost:8020").split(":")[0]

        hdfs_port = int(os.getenv("HADOOP_NAMENODE", "localhost:8020").split(":")[1] if ":" in os.getenv("HADOOP_NAMENODE", "localhost:8020") else "8020")

        hdfs_client = HDFSClient(host=hdfs_host, port=hdfs_port)

        

        # 列出文本块文�?

        chunk_files = hdfs_client.list_files(hdfs_path)

        

        if not chunk_files:

            logger.warning(f"HDFS 路径中没有文件: {hdfs_path}")

            return {

                "success": False,

                "error": f"HDFS 路径中没有文件",

                "file_id": file_id,

                "task_id": task_id,

            }

        

        # 下载并处理每个文本块

        chunks = []

        local_temp_dir = Path("/tmp/chunks")  # 临时目录

        local_temp_dir.mkdir(parents=True, exist_ok=True)

        

        for chunk_file in chunk_files:

            try:

                # 下载文件到本地临时目�?

                local_file = local_temp_dir / Path(chunk_file).name

                hdfs_client.download_file(chunk_file, str(local_file))

                

                # 读取文本内容

                with open(local_file, "r", encoding="utf-8") as f:

                    # 文件格式:文件路径_块编�?\t 文本块内�?

                    line = f.read().strip()

                    if line:

                        parts = line.split('\t', 1)

                        if len(parts) >= 2:

                            chunk_key = parts[0]

                            chunk_text = parts[1]

                            chunks.append({

                                "chunk_id": chunk_key,

                                "text": chunk_text

                            })

                

                # 删除临时文件

                local_file.unlink()

                

            except Exception as e:

                logger.error(f"下载和处理文本块失败: {chunk_file}, 错误: {e}")

                continue

        

        logger.info(f"�?HDFS 下载�?{len(chunks)} 个文本块")

        

        # 调用构建知识图谱任务

        if chunks:

            result = build_knowledge_graph.delay(

                file_id=file_id,

                task_id=task_id,

                chunks=chunks

            )

            return {

                "success": True,

                "file_id": file_id,

                "task_id": task_id,

                "chunks_count": len(chunks),

                "build_task_id": result.id,

            }

        else:

            return {

                "success": False,

                "error": "没有可用的文本块",

                "file_id": file_id,

                "task_id": task_id,

            }

        

    except Exception as e:

        logger.error(f"�?HDFS 下载文本块失�? {hdfs_path}, 错误: {e}")

        raise self.retry(exc=e, countdown=60, max_retries=3)





@celery_app.task(name="backend.celery_tasks.get_task_status")

def get_task_status(task_id: str) -> Dict[str, Any]:

    """

    获取任务状�?

    

    Args:

        task_id: Celery 任务 ID

        

    Returns:

        任务状态信�?

    """

    try:

        from celery.result import AsyncResult

        

        result = AsyncResult(task_id, app=celery_app)

        

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

        logger.error(f"获取任务状态失�? {task_id}, 错误: {e}")

        return {

            "task_id": task_id,

            "status": "ERROR",

            "error": str(e),

        }









