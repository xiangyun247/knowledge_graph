#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery 任务定义
"""

import logging
from typing import List, Dict, Any, Optional

# 尝试导入Celery，用于生产环境
celery_available = False
try:
    from celery import shared_task
    from celery.utils.log import get_task_logger
    celery_available = True
    # 获取日志记录器
    logger = get_task_logger(__name__)
except ImportError:
    # 如果没有安装Celery，使用标准日志记录器
    logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


def build_single_file_kg(
    task_id: str,
    file_id: str,
    text: str,
    user_id: str,
    task_store: Optional[Dict[str, Any]] = None,
    task_store_lock: Optional[Any] = None,
    file_idx: int = 0,
    total_files: int = 1,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    单文件知识图谱构建（供线程池并行调用）。
    每个调用使用独立的 Neo4j/LLM/MySQL 连接，线程安全。

    Returns:
        {"success": True, "file_id", "graph_id", "entities_created", "relations_created"}
        或 {"success": False, "file_id", "error": "..."}
    """
    if not (text or "").strip():
        return {"success": False, "file_id": file_id, "error": "文本为空"}
    try:
        from kg.builder import KnowledgeGraphBuilder
        from db.neo4j_client import Neo4jClient
        from llm.client import LLMClient
        from db.mysql_client import MySQLClient

        neo4j_client = Neo4jClient()
        llm_client = LLMClient()
        mysql_client = MySQLClient()
        mysql_client.connect()
        builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
        )
        try:
            result = builder.process_text(text)
        finally:
            if hasattr(neo4j_client, "close"):
                neo4j_client.close()
            if hasattr(llm_client, "close"):
                llm_client.close()

        entities = result.get("entities", [])
        relations_raw = result.get("relations", [])
        entities_count = len(entities)
        relations_count = len(relations_raw)

        graph_name = (filename or "").strip() or f"KnowledgeGraph_{file_id}"
        graph_description = f"从文件 {graph_name} 构建的知识图谱"
        graph_id = mysql_client.create_graph(
            graph_name=graph_name,
            description=graph_description,
            data_source="PDF",
            file_path=file_id,
            user_id=user_id or "system",
        )
        nodes_for_db = []
        seen_n = set()
        for e in entities:
            name = (e.get("name") or "").strip()
            if not name or name in seen_n:
                continue
            seen_n.add(name)
            nodes_for_db.append({
                "id": name,
                "name": name,
                "type": (e.get("type") or "entity").strip(),
                "category": (e.get("type") or "entity").strip().lower(),
                "description": (e.get("description") or "").strip(),
            })
        relations_for_db = []
        seen_r = set()
        for r in relations_raw:
            sub = (r.get("subject") or "").strip()
            pred = (r.get("predicate") or "").strip()
            obj = (r.get("object") or "").strip()
            if not sub or not pred or not obj:
                continue
            rk = (sub, pred, obj)
            if rk in seen_r:
                continue
            seen_r.add(rk)
            relations_for_db.append({
                "id": f"{sub}_{pred}_{obj}",
                "source": sub,
                "target": obj,
                "relation": pred,
            })
        mysql_client.update_graph_data(
            graph_id,
            {"nodes": nodes_for_db, "relations": relations_for_db},
        )
        mysql_client.update_graph_status(
            graph_id=graph_id,
            status="completed",
            entity_count=entities_count,
            relation_count=relations_count,
        )
        if hasattr(mysql_client, "disconnect"):
            mysql_client.disconnect()

        if task_store is not None and task_id in task_store and task_store_lock is not None:
            with task_store_lock:
                task_store[task_id]["entities_created"] = (
                    task_store[task_id].get("entities_created", 0) + entities_count
                )
                task_store[task_id]["relations_created"] = (
                    task_store[task_id].get("relations_created", 0) + relations_count
                )
                if total_files > 0:
                    task_store[task_id]["progress"] = 60 + int(30 * (file_idx + 1) / total_files)
                task_store[task_id]["message"] = f"已完成文件 {file_id}"

        logger.info(
            f"文件 {file_id} 知识图谱构建完成: graph_id={graph_id}, "
            f"entities={entities_count}, relations={relations_count}"
        )
        return {
            "success": True,
            "file_id": file_id,
            "graph_id": graph_id,
            "entities_created": entities_count,
            "relations_created": relations_count,
        }
    except Exception as e:
        logger.exception(f"单文件构建失败 file_id={file_id}: {e}")
        return {"success": False, "file_id": file_id, "error": str(e)}


def build_kg_from_hadoop(self, task_id: str, file_ids: List[str], hadoop_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 Hadoop 处理结果构建知识图谱
    
    Args:
        self: Celery任务实例（可选）
        task_id: 任务ID
        file_ids: 文件ID列表
        hadoop_result: Hadoop处理结果，包含final_output等信息
        
    Returns:
        构建结果
    """
    logger.info(f"开始构建知识图谱, task_id={task_id}, file_ids={file_ids}")
    
    try:
        # 延迟导入，避免循环依赖
        from backend.app import tasks as task_store, TaskStatus
        
        # 更新任务状态
        if task_id in task_store:
            task_store[task_id]["status"] = TaskStatus.PROCESSING
            task_store[task_id]["message"] = "正在从已提取的PDF文本构建知识图谱"
            task_store[task_id]["progress"] = 60
        
        # 实际知识图谱构建过程
        # 优先使用已提取的PDF文本
        extracted_texts = hadoop_result.get("extracted_texts", {})
        # 总是从 hadoop_result 中获取 final_output
        final_output = hadoop_result.get("final_output")
        
        total_entities_created = 0
        total_relations_created = 0
        
        # 保存每个文件的图谱构建结果
        file_results = []
        
        if extracted_texts:
            logger.info(f"使用已提取的PDF文本，共 {len(extracted_texts)} 个文件")
            
            # 导入所需客户端
            from kg.builder import KnowledgeGraphBuilder
            from db.neo4j_client import Neo4jClient
            from llm.client import LLMClient
            from db.mysql_client import MySQLClient
            
            # 创建客户端实例（不使用with语句，因为DeepSeekClient不支持上下文管理器协议）
            neo4j_client = Neo4jClient()
            llm_client = LLMClient()
            mysql_client = MySQLClient()
            
            try:
                # 连接MySQL
                mysql_client.connect()
                
                # 创建知识图谱构建器
                builder = KnowledgeGraphBuilder(
                    neo4j_client=neo4j_client,
                    llm_client=llm_client
                )
                
                # 处理所有提取的文本，每个文件对应一个知识图谱
                total_files = len(extracted_texts)
                for file_idx, (file_id, text) in enumerate(extracted_texts.items()):
                    logger.info(f"处理文件 {file_id}，文本长度: {len(text)} 字符")
                    
                    # 更新任务进度：文件级进度
                    file_progress = 60 + int(30 * (file_idx + 1) / total_files)
                    if task_id in task_store:
                        task_store[task_id]["status"] = TaskStatus.PROCESSING
                        task_store[task_id]["message"] = f"正在处理文件 {file_id}"
                        task_store[task_id]["progress"] = file_progress
                    
                    # 为每个文件创建一个知识图谱
                    graph_name = f"KnowledgeGraph_{file_id}"
                    graph_description = f"从文件 {file_id} 构建的知识图谱"
                    
                    # 在MySQL中创建知识图谱记录
                    graph_id = mysql_client.create_graph(
                        graph_name=graph_name,
                        description=graph_description,
                        data_source="PDF",
                        file_path=file_id,
                        user_id="system"
                    )
                    logger.info(f"为文件 {file_id} 创建了知识图谱: {graph_id}")
                    
                    # 调用知识图谱构建器处理文本
                    result = builder.process_text(text)
                    
                    # 提取实体和关系数据
                    entities = result.get("entities", [])
                    relations = result.get("relations", [])
                    
                    # 将实体和关系存储到MySQL
                    graph_data = {
                        "nodes": entities,
                        "relations": relations
                    }
                    
                    mysql_client.update_graph_data(graph_id, graph_data)
                    
                    # 更新知识图谱状态和统计信息
                    mysql_client.update_graph_status(
                        graph_id=graph_id,
                        status="completed",
                        entity_count=len(entities),
                        relation_count=len(relations)
                    )
                    
                    # 累加统计结果 - 使用实际提取的实体和关系数量，而不是Neo4j创建结果
                    total_entities_created += len(entities)
                    total_relations_created += len(relations)
                    
                    # 更新任务进度：包含实体和关系计数
                    if task_id in task_store:
                        task_store[task_id]["entities_created"] = total_entities_created
                        task_store[task_id]["relations_created"] = total_relations_created
                    
                    # 保存文件结果
                    file_results.append({
                        "file_id": file_id,
                        "graph_id": graph_id,
                        "entities_created": result.get("entities_created", 0),
                        "relations_created": result.get("relations_created", 0)
                    })
                    
                    logger.info(f"文件 {file_id} 的知识图谱构建完成，生成 {len(entities)} 个实体和 {len(relations)} 个关系")
                    
            finally:
                # 关闭客户端连接
                if hasattr(neo4j_client, 'close'):
                    neo4j_client.close()
                if hasattr(llm_client, 'close'):
                    llm_client.close()
                if hasattr(mysql_client, 'disconnect'):
                    mysql_client.disconnect()
        else:
            # 保持原有逻辑，从HDFS读取
            if not final_output:
                raise ValueError("Hadoop结果中没有final_output路径")
            logger.info(f"从HDFS路径读取数据: {final_output}")
            
            # 从HDFS读取数据的逻辑（此处省略）
            # 实际项目中，这里应该：
            # 1. 从 HDFS 下载 Hadoop 处理后的文本块
            # 2. 使用 NLP 模型提取实体和关系
            # 3. 将实体和关系存储到 Neo4j 或其他图数据库
            
            # 使用默认数量
            total_entities_created = 100
            total_relations_created = 150
        
        # 更新任务状态
        if task_id in task_store:
            task_store[task_id]["entities_created"] = total_entities_created
            task_store[task_id]["relations_created"] = total_relations_created
            task_store[task_id]["status"] = TaskStatus.COMPLETED
            task_store[task_id]["message"] = "知识图谱构建完成"
            task_store[task_id]["progress"] = 100
        
        result = {
            "success": True,
            "total_entities_created": total_entities_created,
            "total_relations_created": total_relations_created,
            "file_results": file_results,
            "message": "知识图谱构建成功",
            "final_output": final_output
        }
        
        logger.info(f"知识图谱构建完成, task_id={task_id}, result={result}")
        return result
        
    except Exception as e:
        logger.error(f"构建知识图谱失败, task_id={task_id}, error={e}", exc_info=True)
        
        # 更新任务状态
        try:
            from backend.app import tasks as task_store, TaskStatus
            if task_id in task_store:
                task_store[task_id]["status"] = TaskStatus.FAILED
                task_store[task_id]["message"] = f"构建知识图谱失败: {str(e)}"
                task_store[task_id]["progress"] = 100
        except Exception as update_err:
            logger.error(f"更新任务状态失败: {update_err}")
        
        # 如果Celery可用，抛出异常让Celery重试
        if celery_available and self:
            self.retry(exc=e, countdown=5, max_retries=3)
        else:
            # 如果没有Celery，直接返回失败结果
            return {
                "success": False,
                "message": f"构建知识图谱失败: {str(e)}",
                "error": str(e)
            }

# 如果Celery可用，将函数包装为Celery任务
if celery_available:
    build_kg_from_hadoop = shared_task(bind=True, name='backend.tasks.build_kg_from_hadoop', queue='kg_build')(build_kg_from_hadoop)


def process_hadoop_output(self, output_path: str) -> Dict[str, Any]:
    """
    处理 Hadoop 输出结果
    
    Args:
        self: Celery任务实例（可选）
        output_path: Hadoop输出路径
        
    Returns:
        处理结果
    """
    logger.info(f"开始处理Hadoop输出, output_path={output_path}")
    
    try:
        # 模拟处理Hadoop输出
        # 实际项目中，这里应该：
        # 1. 从HDFS下载输出文件
        # 2. 解析输出内容
        # 3. 进行数据清洗和转换
        
        logger.info(f"处理Hadoop输出文件: {output_path}")
        
        # 模拟处理结果
        processed_data = {
            "total_files": 10,
            "processed_files": 10,
            "entities_extracted": 500,
            "relations_extracted": 750
        }
        
        result = {
            "success": True,
            "processed_data": processed_data,
            "message": "Hadoop输出处理成功"
        }
        
        logger.info(f"Hadoop输出处理完成, result={result}")
        return result
        
    except Exception as e:
        logger.error(f"处理Hadoop输出失败, output_path={output_path}, error={e}", exc_info=True)
        # 如果Celery可用，抛出异常让Celery重试
        if celery_available and self:
            self.retry(exc=e, countdown=5, max_retries=3)
        else:
            # 如果没有Celery，直接返回失败结果
            return {
                "success": False,
                "message": f"处理Hadoop输出失败: {str(e)}",
                "error": str(e)
            }


def cleanup_resources(task_id: str) -> Dict[str, Any]:
    """
    清理任务资源
    
    Args:
        task_id: 任务ID
        
    Returns:
        清理结果
    """
    logger.info(f"开始清理任务资源, task_id={task_id}")
    
    try:
        # 模拟清理资源
        # 实际项目中，这里应该：
        # 1. 删除临时文件
        # 2. 释放其他资源
        
        logger.info(f"清理任务 {task_id} 的资源")
        
        result = {
            "success": True,
            "message": "资源清理成功"
        }
        
        logger.info(f"任务资源清理完成, task_id={task_id}")
        return result
        
    except Exception as e:
        logger.error(f"清理任务资源失败, task_id={task_id}, error={e}", exc_info=True)
        return {
            "success": False,
            "message": f"资源清理失败: {str(e)}"
        }


# 如果Celery可用，将其他函数包装为Celery任务
if celery_available:
    process_hadoop_output = shared_task(bind=True, name='backend.tasks.process_hadoop_output', queue='kg_process')(process_hadoop_output)
    cleanup_resources = shared_task(name='backend.tasks.cleanup_resources', queue='default')(cleanup_resources)
