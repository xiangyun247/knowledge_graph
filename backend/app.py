#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱系统后端API
"""

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
import uuid
import threading
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import time

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from db.mysql_client import get_mysql_client

# 尝试导入 Neo4j 客户端（可选，用于实体搜索）
neo4j_client = None
try:
    from db.neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient()
    if neo4j_client.verify_connection():
        logger.info("Neo4j客户端初始化成功，实体搜索将使用Neo4j")
    else:
        neo4j_client = None
        logger.warning("Neo4j连接验证失败，实体搜索将回退到MySQL")
except Exception as e:
    logger.warning(f"Neo4j客户端初始化失败: {e}，实体搜索将使用MySQL")

# 初始化 RAG 相关组件（用于智能问答）
rag_pipeline = None
llm_client = None
embedding_client = None
try:
    from llm.client import LLMClient, EmbeddingClient
    from rag.rag_pipeline import RAGPipeline
    
    # 初始化 LLM 客户端
    llm_client = LLMClient()
    if llm_client.verify_connection():
        logger.info("LLM客户端初始化成功")
    else:
        llm_client = None
        logger.warning("LLM连接验证失败，智能问答功能可能不可用")
    
    # 初始化 Embedding 客户端
    embedding_client = EmbeddingClient()
    logger.info("Embedding客户端初始化成功")
    
    # 初始化 RAG 流水线（需要 Neo4j 和 LLM）
    if neo4j_client and llm_client:
        rag_pipeline = RAGPipeline(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )
        logger.info("RAG流水线初始化成功，智能问答功能可用")
    else:
        logger.warning("RAG流水线初始化失败：缺少必要的客户端（Neo4j 或 LLM）")
except Exception as e:
    logger.warning(f"RAG组件初始化失败: {e}，智能问答功能可能不可用")

# 创建FastAPI应用
app = FastAPI(
    title="知识图谱系统API",
    description="知识图谱系统后端API接口文档",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# 初始化日志配置
# 使用 enqueue=True 和 catch=True 避免 Windows 上的文件锁定问题
logger.add(
    "logs/app.log",
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    enqueue=True,  # 使用队列异步写入，避免文件锁定
    catch=True,    # 捕获并忽略日志写入错误，避免影响程序运行
    backtrace=False,  # 不记录回溯信息，减少日志大小
    diagnose=False    # 不记录诊断信息，减少日志大小
)

# 初始化MySQL客户端（延迟加载）
mysql_client = None
try:
    mysql_client = get_mysql_client()
    logger.info("MySQL客户端初始化成功")
except Exception as e:
    logger.error(f"MySQL客户端初始化失败: {e}")
    logger.warning("应用将在没有MySQL的情况下运行，部分功能可能不可用")


# 定义任务状态枚举
class TaskStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 全局存储
uploaded_files = {}
"""
上传文件存储字典
格式: {file_id: {"filename": str, "path": str, "size": int, "uploaded_at": str, "content": str}}
"""

tasks = {}
"""
任务状态存储字典
格式: {task_id: {"status": str, "progress": int, "current_chunk": int, "total_chunks": int, "entities_created": int, "relations_created": int, "message": str, "current_processing": str, "file_id": str}}
"""

history_records = {}
"""
历史记录存储字典
格式: {record_id: {"id": str, "type": str, "file_id": str, "file_name": str, "task_id": str, "status": str, "message": str, "created_at": str, "processed_at": str}}
"""

history_counter = 1
"""历史记录ID计数器"""


class BuildKGFromFileRequest(BaseModel):
    """从前端接收构建知识图谱请求体"""
    file_id: str = Field(..., description="已上传文件的ID")

# 文件上传API
@app.post("/api/upload", tags=["文件上传"])
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件
    """
    try:
        # 生成唯一文件ID
        file_id = str(uuid.uuid4())
        
        # 保存文件到本地（保留原始文件扩展名）
        file_ext = os.path.splitext(file.filename)[1] if '.' in file.filename else ''
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
        content = b''
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 每次读取1MB
                if not chunk:
                    break
                content += chunk
                f.write(chunk)
        
        # 存储文件信息
        uploaded_files[file_id] = {
            "filename": file.filename,
            "path": file_path,  # 保存完整路径，包含扩展名
            "size": len(content),
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content.decode("utf-8", errors="ignore") if isinstance(content, bytes) and file_ext.lower() != '.pdf' else None  # PDF 不存储文本内容
        }
        
        logger.info(f"文件上传成功: {file.filename} (ID: {file_id})")
        
        # 保存上传记录到MySQL或内存
        if mysql_client:
            try:
                history_id = mysql_client.create_history_record(
                    file_id=file_id,
                    file_name=file.filename,
                    file_type="upload",
                    task_id=file_id
                )
                logger.info(f"上传记录已保存到MySQL: {history_id}")
            except Exception as e:
                logger.error(f"保存上传记录到MySQL失败: {str(e)}")
        else:
            # 使用内存存储保存记录
            global history_counter
            history_id = str(history_counter)
            history_counter += 1
            
            history_records[history_id] = {
                "id": history_id,
                "type": "upload",
                "file_id": file_id,
                "file_name": file.filename,
                "task_id": file_id,
                "status": "success",
                "message": "文件上传成功",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logger.info(f"上传记录已保存到内存: {history_id}")
        
        return {
            "status": "success",
            "file_id": file_id,
            "filename": file.filename,
            "message": "文件上传成功"
        }
        
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

# 从文件生成知识图谱API
@app.post("/api/kg/build", tags=["知识图谱构建"])
async def build_kg_from_file(request: BuildKGFromFileRequest):
    """
    从上传的文件生成知识图谱（异步）
    """
    try:
        file_id = request.file_id
        
        # 检查文件是否存在
        if file_id not in uploaded_files:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务信息
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": "任务已创建，开始处理",
            "current_processing": "初始化",
            "file_id": file_id
        }
        
        # 启动后台线程处理任务
        thread = threading.Thread(target=build_kg_background, args=(task_id, file_id))
        thread.start()
        
        logger.info(f"知识图谱构建任务已启动: {task_id} (文件: {file_id})")
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": "知识图谱构建任务已启动"
        }
        
    except Exception as e:
        logger.error(f"启动知识图谱构建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


# 查询知识图谱构建进度API
@app.get("/api/kg/build/progress/{task_id}", tags=["知识图谱构建"])
async def get_build_progress(task_id: str):
    """
    查询知识图谱构建进度
    
    Args:
        task_id: 任务ID（可能是 task_id 或 file_id）
    """
    try:
        # 首先检查内存中的任务
        if task_id in tasks:
            task_info = tasks[task_id]
            logger.debug(f"查询任务进度: task_id={task_id}, status={task_info.get('status')}, progress={task_info.get('progress')}")
            return {
                "status": "success",
                "data": task_info
            }
        
        # 如果内存中没有，尝试从 MySQL 查询已完成的任务
        # task_id 可能是 file_id，需要根据 file_id 查找对应的图谱
        if mysql_client:
            try:
                # 尝试根据 file_id 查找图谱
                graphs = mysql_client.get_graphs(limit=100, offset=0)
                for graph in graphs:
                    # 检查 data_source 是否匹配 file_id
                    if graph.get("data_source") == task_id:
                        # 找到对应的图谱，返回完成状态
                        return {
                            "status": "success",
                            "data": {
                                "status": "completed",
                                "progress": 100,
                                "entities_created": graph.get("entity_count", 0),
                                "relations_created": graph.get("relation_count", 0),
                                "message": f"知识图谱构建完成！共创建 {graph.get('entity_count', 0)} 个实体，{graph.get('relation_count', 0)} 个关系",
                                "current_processing": "完成",
                                "file_id": task_id,
                                "graph_id": graph.get("graph_id")
                            }
                        }
            except Exception as e:
                logger.warning(f"从 MySQL 查询任务状态失败: {e}")
        
        # 如果都找不到，返回任务不存在（但使用更友好的状态）
        # 前端应该处理这种情况，停止轮询
        return {
            "status": "success",
            "data": {
                "status": "not_found",
                "progress": 0,
                "message": "任务不存在或已过期（后端可能已重启）",
                "current_processing": "未知"
            }
        }
    except Exception as e:
        logger.error(f"查询构建进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询进度失败: {str(e)}")

# 后台知识图谱构建函数
def build_kg_background(task_id: str, file_id: str):
    """
    后台线程处理知识图谱构建任务
    支持 PDF 和 TXT 文件
    """
    try:
        # 获取文件信息
        if file_id not in uploaded_files:
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "文件不存在",
                "current_processing": "",
                "file_id": file_id
            }
            return
        
        file_info = uploaded_files[file_id]
        filename = file_info["filename"]
        file_path = file_info["path"]
        
        # 更新任务状态：初始化
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 5,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": "正在初始化知识图谱构建器...",
            "current_processing": "初始化",
            "file_id": file_id
        }
        
        # 初始化知识图谱构建器
        from kg.builder import KnowledgeGraphBuilder
        
        if not neo4j_client:
            raise Exception("Neo4j 客户端未初始化")
        if not llm_client:
            raise Exception("LLM 客户端未初始化")
        
        kg_builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client
        )
        
        # 根据文件类型处理
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        entities_count = 0
        relations_count = 0
        total_chunks = 0
        processed_chunks = 0
        
        # 记录处理前的节点和关系数量（用于后续收集当前图谱的数据）
        # 必须在处理开始前记录，确保在所有文件类型处理中都能使用
        nodes_before = set()
        edges_before = set()
        if neo4j_client:
            try:
                # 记录处理前的数据
                neo4j_data_before = neo4j_client.get_all_nodes_and_relationships()
                nodes_before = {str(node.get("id", "")) for node in neo4j_data_before.get('nodes', [])}
                edges_before = {(str(rel.get("source", "")), str(rel.get("target", "")), str(rel.get("type", rel.get("label", "")))) 
                               for rel in neo4j_data_before.get('relationships', [])}
                logger.info(f"记录处理前的数据: {len(nodes_before)} 个节点, {len(edges_before)} 个关系")
            except Exception as e:
                logger.warning(f"无法记录处理前的数据: {e}")
        
        if file_ext == 'pdf':
            # 处理 PDF 文件
            tasks[task_id] = {
                "status": TaskStatus.PROCESSING,
                "progress": 10,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "正在提取 PDF 文本...",
                "current_processing": "PDF 文本提取",
                "file_id": file_id
            }
            
            # 导入 PDF 处理函数
            from scripts.import_pdf import extract_text_from_pdf, clean_medical_text
            
            # 提取 PDF 文本
            raw_text = extract_text_from_pdf(file_path)
            
            # 清洗文本
            tasks[task_id] = {
                "status": TaskStatus.PROCESSING,
                "progress": 20,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "正在清洗文本...",
                "current_processing": "文本清洗",
                "file_id": file_id
            }
            
            clean_text = clean_medical_text(raw_text)
            
            if not clean_text.strip():
                raise Exception("清洗后文本内容为空")
            
            # 分段处理（每段约1000字符）
            chunk_size = 1000
            chunks = [
                clean_text[i:i + chunk_size]
                for i in range(0, len(clean_text), chunk_size)
            ]
            total_chunks = len(chunks)
            
            tasks[task_id] = {
                "status": TaskStatus.PROCESSING,
                "progress": 30,
                "current_chunk": 0,
                "total_chunks": total_chunks,
                "entities_created": 0,
                "relations_created": 0,
                "message": f"开始处理 {total_chunks} 个文本段...",
                "current_processing": "知识图谱构建",
                "file_id": file_id
            }
            
            # 逐段处理
            for idx, chunk in enumerate(chunks, start=1):
                try:
                    result = kg_builder.process_text(chunk)
                    
                    # 更新统计
                    chunk_entities = result.get("entities_created", 0) or result.get("entity_count", 0) or 0
                    chunk_relations = result.get("relations_created", 0) or result.get("relation_count", 0) or 0
                    
                    entities_count += chunk_entities
                    relations_count += chunk_relations
                    processed_chunks += 1
                    
                    # 更新进度
                    progress = 30 + int((idx / total_chunks) * 60)
                    tasks[task_id] = {
                        "status": TaskStatus.PROCESSING,
                        "progress": progress,
                        "current_chunk": idx,
                        "total_chunks": total_chunks,
                        "entities_created": entities_count,
                        "relations_created": relations_count,
                        "message": f"已处理 {idx}/{total_chunks} 段，新增实体 {chunk_entities}，关系 {chunk_relations}",
                        "current_processing": f"处理第 {idx} 段",
                        "file_id": file_id
                    }
                    
                    logger.info(f"处理第 {idx}/{total_chunks} 段完成: 实体={chunk_entities}, 关系={chunk_relations}")
                    
                except Exception as e:
                    logger.error(f"处理第 {idx} 段失败: {e}")
                    # 继续处理下一段
                    continue
        
        elif file_ext in ['txt', 'text']:
            # 处理文本文件
            tasks[task_id] = {
                "status": TaskStatus.PROCESSING,
                "progress": 20,
                "current_chunk": 0,
                "total_chunks": 1,
                "entities_created": 0,
                "relations_created": 0,
                "message": "正在读取文本文件...",
                "current_processing": "文件读取",
                "file_id": file_id
            }
            
            # 读取文本内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
            
            # 分段处理
            chunk_size = 1000
            chunks = [
                text_content[i:i + chunk_size]
                for i in range(0, len(text_content), chunk_size)
            ]
            total_chunks = len(chunks)
            
            tasks[task_id] = {
                "status": TaskStatus.PROCESSING,
                "progress": 30,
                "current_chunk": 0,
                "total_chunks": total_chunks,
                "entities_created": 0,
                "relations_created": 0,
                "message": f"开始处理 {total_chunks} 个文本段...",
                "current_processing": "知识图谱构建",
                "file_id": file_id
            }
            
            # 逐段处理
            for idx, chunk in enumerate(chunks, start=1):
                try:
                    result = kg_builder.process_text(chunk)
                    
                    chunk_entities = result.get("entities_created", 0) or result.get("entity_count", 0) or 0
                    chunk_relations = result.get("relations_created", 0) or result.get("relation_count", 0) or 0
                    
                    entities_count += chunk_entities
                    relations_count += chunk_relations
                    processed_chunks += 1
                    
                    progress = 30 + int((idx / total_chunks) * 60)
                    tasks[task_id] = {
                        "status": TaskStatus.PROCESSING,
                        "progress": progress,
                        "current_chunk": idx,
                        "total_chunks": total_chunks,
                        "entities_created": entities_count,
                        "relations_created": relations_count,
                        "message": f"已处理 {idx}/{total_chunks} 段",
                        "current_processing": f"处理第 {idx} 段",
                        "file_id": file_id
                    }
                    
                except Exception as e:
                    logger.error(f"处理第 {idx} 段失败: {e}")
                    continue
        
        else:
            raise Exception(f"不支持的文件类型: {file_ext}")
        
        # 更新任务状态：正在保存数据
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 95,
            "current_chunk": processed_chunks,
            "total_chunks": total_chunks,
            "entities_created": entities_count,
            "relations_created": relations_count,
            "message": "正在保存图谱数据到数据库...",
            "current_processing": "保存数据",
            "file_id": file_id
        }
        logger.info(f"文本处理完成，开始保存数据: task_id={task_id}, entities={entities_count}, relations={relations_count}")
        
        # 将知识图谱记录存储到MySQL
        graph_id = None
        if mysql_client:
            try:
                graph_id = mysql_client.create_graph(
                    graph_name=filename,
                    description=f"从文件 {filename} 生成的知识图谱",
                    data_source=file_id,
                    file_path=file_path,
                    user_id="default_user"
                )
                
                # 从 Neo4j 收集当前图谱的节点和关系数据
                # 通过对比处理前后的数据，只收集新增的节点和关系
                if neo4j_client:
                    try:
                        logger.info(f"正在从 Neo4j 收集图谱 {graph_id} 的数据...")
                        neo4j_data = neo4j_client.get_all_nodes_and_relationships()
                        all_nodes = neo4j_data.get('nodes', [])
                        all_relationships = neo4j_data.get('relationships', [])
                        
                        # 只收集新增的节点和关系（处理前不存在的）
                        # 确保节点ID是字符串格式，以便正确匹配
                        nodes = []
                        for node in all_nodes:
                            node_id = str(node.get("id", ""))
                            if node_id not in nodes_before:
                                nodes.append(node)
                        
                        # 确保关系匹配时使用正确的格式
                        relationships = []
                        for rel in all_relationships:
                            source = str(rel.get("source", ""))
                            target = str(rel.get("target", ""))
                            rel_type = str(rel.get("type", rel.get("label", "")))
                            edge_key = (source, target, rel_type)
                            if edge_key not in edges_before:
                                relationships.append(rel)
                        
                        logger.info(f"处理前: {len(nodes_before)} 个节点, {len(edges_before)} 个关系")
                        logger.info(f"处理后: {len(all_nodes)} 个节点, {len(all_relationships)} 个关系")
                        logger.info(f"收集到新增节点: {len(nodes)} 个，新增关系: {len(relationships)} 个")
                        
                        # 转换关系格式为 edges
                        edges = []
                        for rel in relationships:
                            edge = {
                                "id": rel.get("id", ""),
                                "source": rel.get("source", ""),
                                "target": rel.get("target", ""),
                                "label": rel.get("label", rel.get("type", "")),
                                "type": rel.get("type", rel.get("label", "")),
                                "properties": rel.get("properties", {})
                            }
                            edges.append(edge)
                        
                        # 保存到 MySQL 的 graph_data 字段
                        graph_data = {
                            "nodes": nodes,
                            "edges": edges
                        }
                        mysql_client.update_graph_data(graph_id, graph_data)
                        logger.info(f"成功保存图谱数据到 MySQL: {len(nodes)} 个节点, {len(edges)} 个关系")
                    except Exception as e:
                        logger.error(f"从 Neo4j 收集或保存数据失败: {str(e)}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # 即使收集失败，也继续保存元数据
                
                # 更新图谱状态（无论 graph_data 是否保存成功）
                try:
                    mysql_client.update_graph_status(
                        graph_id=graph_id,
                        status="completed",
                        entity_count=entities_count,
                        relation_count=relations_count
                    )
                    logger.info(f"知识图谱记录已存储到MySQL: {graph_id}")
                except Exception as e:
                    logger.error(f"更新图谱状态失败: {str(e)}")
            except Exception as e:
                logger.error(f"存储知识图谱记录到MySQL失败: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        # 所有操作完成后，更新任务状态为完成
        tasks[task_id] = {
            "status": TaskStatus.COMPLETED,
            "progress": 100,
            "current_chunk": processed_chunks,
            "total_chunks": total_chunks,
            "entities_created": entities_count,
            "relations_created": relations_count,
            "message": f"知识图谱构建成功！共创建 {entities_count} 个实体，{relations_count} 个关系",
            "current_processing": "完成",
            "file_id": file_id,
            "graph_id": graph_id
        }
        logger.info(f"任务状态已更新为完成: task_id={task_id}, status={TaskStatus.COMPLETED}, progress=100, graph_id={graph_id}")
        
    except Exception as e:
        logger.error(f"知识图谱构建失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        tasks[task_id] = {
            "status": TaskStatus.FAILED,
            "progress": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": f"构建失败: {str(e)}",
            "current_processing": "",
            "file_id": file_id
        }

from pydantic import BaseModel


class ChatHistoryCreate(BaseModel):
    """用于保存聊天历史的请求模型"""
    id: int
    type: str
    title: str
    content: Dict[str, Any]
    status: str
    entities: List[Any] = []
    createTime: str
    updateTime: str


@app.get("/api/history/list", tags=["历史记录"])
async def get_history_list(type: Optional[str] = None, status: Optional[str] = None):
    """
    获取历史记录列表

    当存在 MySQL 客户端时，仅从数据库读取格式化后的历史记录；
    如果没有 MySQL，则退回到仅使用内存中的 history_records。
    """
    try:
        history_list: List[Dict[str, Any]] = []

        # 1. 如果有 MySQL，优先只用数据库中的历史记录（已按前端结构转换）
        if mysql_client:
            history_list = mysql_client.get_histories()
        else:
            # 2. 否则仅使用内存中的历史记录
            history_list = list(history_records.values())

        # 3. 统一按类型、状态过滤
        if type:
            history_list = [record for record in history_list if record.get("type") == type]

        if status:
            history_list = [record for record in history_list if record.get("status") == status]

        return {
            "status": "success",
            "data": {
                "list": history_list,
                "total": len(history_list)
            }
        }
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")

# 获取历史记录统计API
@app.get("/api/history/stats", tags=["历史记录"])
async def get_history_stats():
    """
    获取历史记录统计信息
    """
    try:
        if mysql_client:
            stats = mysql_client.get_history_stats()
            return {
                "status": "success",
                "data": stats
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except Exception as e:
        logger.error(f"获取历史记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史记录统计失败: {str(e)}")


@app.post("/api/history/save", tags=["历史记录"])
async def save_history(record: ChatHistoryCreate):
    """
    保存聊天/图谱/上传等历史记录
    当前实现：
    - 如果配置了 MySQL，则尝试写入 MySQL（需要 mysql_client 支持对应方法）；
    - 否则先写入内存 history_records，保证前端不报错。
    """
    try:
        global history_counter

        # 转成通用 dict
        record_dict = record.model_dump()

        # 内存中的 ID 统一用字符串，方便前端展示
        history_id = str(record_dict.get("id") or history_counter)

        # 映射一些字段名以便后续扩展
        stored = {
            "id": history_id,
            "type": record_dict.get("type", "chat"),
            "title": record_dict.get("title", ""),
            "content": record_dict.get("content", {}),
            "status": record_dict.get("status", "completed"),
            "entities": record_dict.get("entities", []),
            "created_at": record_dict.get("createTime"),
            "updated_at": record_dict.get("updateTime"),
        }

        # 优先尝试保存到 MySQL（使用已有的 save_history_record 方法）
        if mysql_client and hasattr(mysql_client, "save_history_record"):
            try:
                mysql_id = mysql_client.save_history_record(stored)
                # 如果 MySQL 返回了新的 ID，则覆盖本地 ID
                if mysql_id:
                    stored["id"] = str(mysql_id)
                # 已成功写入数据库时，不再写入内存，避免重复与 ID 冲突
            except Exception as e:
                logger.error(f"保存聊天历史到 MySQL 失败: {e}")
                # 回退到内存存储
                history_records[history_id] = stored
                history_counter += 1
        else:
            # 没有 MySQL 时仅使用内存存储
            history_records[history_id] = stored
            history_counter += 1

        return {
            "status": "success",
            "data": stored
        }

    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存历史记录失败: {str(e)}")

# 获取知识图谱列表API
@app.get("/api/kg/list", tags=["知识图谱"])
async def get_kg_list():
    """
    获取已生成的知识图谱列表
    """
    try:
        if mysql_client:
            # 查询所有知识图谱记录
            kg_records = mysql_client.get_graphs()
            
            # 转换为前端期望的格式
            formatted_records = []
            for record in kg_records:
                formatted_records.append({
                    "id": record.get('graph_id', ''),
                    "name": record.get('graph_name', ''),
                    "description": record.get('description', ''),
                    "file_path": record.get('file_path', ''),
                    "status": record.get('status', ''),
                    "entities_count": record.get('entity_count', 0),
                    "relations_count": record.get('relation_count', 0),
                    "created_at": record.get('created_at', '')
                })
            
            return {
                "status": "success",
                "data": {
                    "list": formatted_records,
                    "total": len(formatted_records)
                }
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except Exception as e:
        logger.error(f"获取知识图谱列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱列表失败: {str(e)}")

# 获取知识图谱详情API
@app.get("/api/kg/{graph_id}", tags=["知识图谱"])
async def get_kg_detail(graph_id: str):
    """
    获取知识图谱详情
    """
    try:
        if mysql_client:
            kg_record = mysql_client.get_graph_by_id(graph_id)
            if not kg_record:
                raise HTTPException(status_code=404, detail="知识图谱不存在")
            
            # 转换为前端期望的格式
            formatted_record = {
                "id": kg_record.get('graph_id', ''),
                "name": kg_record.get('graph_name', ''),
                "description": kg_record.get('description', ''),
                "file_path": kg_record.get('file_path', ''),
                "status": kg_record.get('status', ''),
                "entities_count": kg_record.get('entity_count', 0),
                "relations_count": kg_record.get('relation_count', 0),
                "created_at": kg_record.get('created_at', '')
            }
            
            return {
                "status": "success",
                "data": formatted_record
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱详情失败: {str(e)}")

# 获取知识图谱可视化数据API
@app.get("/api/kg/{graph_id}/visualize", tags=["知识图谱"])
async def get_kg_visualize_data(graph_id: str):
    """
    获取知识图谱可视化数据（节点和关系）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "nodes": [],
                    "relations": [],
                    "total_nodes": 0,
                    "total_relations": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取节点和关系数据
        nodes = graph_data.get("nodes", [])
        relations = graph_data.get("relations", [])
        
        return {
            "status": "success",
            "data": {
                "nodes": nodes,
                "relations": relations,
                "total_nodes": len(nodes),
                "total_relations": len(relations)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱可视化数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱可视化数据失败: {str(e)}")

# 获取知识图谱节点列表API
@app.get("/api/kg/{graph_id}/nodes", tags=["知识图谱"])
async def get_kg_nodes(graph_id: str):
    """
    获取知识图谱节点列表
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取节点数据
        nodes = graph_data.get("nodes", [])
        
        return {
            "status": "success",
            "data": {
                "list": nodes,
                "total": len(nodes)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱节点列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱节点列表失败: {str(e)}")

# 获取知识图谱关系列表API
@app.get("/api/kg/{graph_id}/relations", tags=["知识图谱"])
async def get_kg_relations(graph_id: str):
    """
    获取知识图谱关系列表
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取关系数据
        relations = graph_data.get("relations", [])
        
        return {
            "status": "success",
            "data": {
                "list": relations,
                "total": len(relations)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱关系列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱关系列表失败: {str(e)}")

# 获取图谱列表（用于前端切换）
@app.get("/api/graph/list", tags=["知识图谱"])
async def get_graph_list(
    status: Optional[str] = Query(None, description="图谱状态过滤"),
    limit: Optional[int] = Query(100, description="返回数量限制"),
    offset: Optional[int] = Query(0, description="偏移量")
):
    """
    获取知识图谱列表
    
    Returns:
        图谱列表，包含 graph_id, graph_name, description, entity_count, relation_count 等
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        graphs = mysql_client.get_graphs(status=status, limit=limit, offset=offset)
        
        # 格式化返回数据
        graph_list = []
        for graph in graphs:
            graph_list.append({
                "graph_id": graph.get("graph_id", ""),
                "graph_name": graph.get("graph_name", ""),
                "description": graph.get("description", ""),
                "status": graph.get("status", ""),
                "entity_count": graph.get("entity_count", 0),
                "relation_count": graph.get("relation_count", 0),
                "created_at": graph.get("created_at", ""),
                "file_path": graph.get("file_path", "")
            })
        
        return {
            "status": "success",
            "data": {
                "list": graph_list,
                "total": len(graph_list)
            }
        }
    except Exception as e:
        logger.error(f"获取图谱列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取图谱列表失败: {str(e)}")

def sync_graph_data_to_neo4j(graph_data: Dict[str, Any], neo4j_client_instance):
    """
    将 MySQL 中的图谱数据同步到 Neo4j
    
    Args:
        graph_data: 图谱数据字典，包含 nodes 和 edges
        neo4j_client_instance: Neo4j 客户端实例
    """
    try:
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        if not nodes:
            logger.warning("没有节点数据需要同步")
            return
        
        logger.info(f"开始同步 {len(nodes)} 个节点和 {len(edges)} 个关系到 Neo4j...")
        
        # 先清空 Neo4j（可选，根据需求决定是否清空）
        # neo4j_client_instance.delete_all()
        
        # 同步节点
        for node in nodes:
            try:
                # 优先从 category 或 type 获取节点类型
                node_type = node.get("category") or node.get("type")
                node_name = node.get("name", node.get("label", ""))
                node_props = node.get("properties", {})
                
                if not node_name:
                    continue
                
                # 如果节点类型为空，尝试从 properties 中获取
                if not node_type:
                    node_type = node_props.get("category") or node_props.get("type") or "Entity"
                
                # 确保 node_type 是有效的 Neo4j 标签（只包含字母、数字和下划线）
                import re
                clean_node_type = re.sub(r'[^a-zA-Z0-9_]', '', str(node_type))
                if not clean_node_type:
                    clean_node_type = "Entity"
                
                # 在 properties 中保存原始类型信息
                props = {"name": node_name, "type": node_type, "category": node_type, **node_props}
                
                # 创建节点（使用清理后的类型作为 label）
                query = f"""
                MERGE (n:{clean_node_type} {{name: $name}})
                ON CREATE SET n = $props, n.created_at = datetime()
                ON MATCH SET n = $props, n.updated_at = datetime()
                RETURN n
                """
                neo4j_client_instance.execute_write(query, {"name": node_name, "props": props})
                
                # 记录前几个节点的同步信息
                if len([n for n in nodes if n == node]) <= 3:
                    logger.debug(f"同步节点: name={node_name}, type={node_type}, clean_type={clean_node_type}")
            except Exception as e:
                logger.warning(f"同步节点失败: {node} - {e}")
                import traceback
                logger.warning(traceback.format_exc())
        
        # 同步关系
        for edge in edges:
            try:
                source_id = edge.get("source", "")
                target_id = edge.get("target", "")
                rel_type = edge.get("label", edge.get("type", "RELATED_TO"))
                rel_props = edge.get("properties", {})
                
                if not source_id or not target_id:
                    continue
                
                # 创建关系（需要先找到对应的节点）
                # 注意：这里假设 source_id 和 target_id 是节点名称或 Neo4j 内部 ID
                query = f"""
                MATCH (a), (b)
                WHERE (id(a) = $source_id OR a.name = $source_name)
                  AND (id(b) = $target_id OR b.name = $target_name)
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r = $props, r.created_at = datetime()
                ON MATCH SET r = $props, r.updated_at = datetime()
                RETURN r
                """
                
                # 尝试将 source_id 和 target_id 转换为整数（如果是 Neo4j 内部 ID）
                try:
                    source_id_int = int(source_id)
                    target_id_int = int(target_id)
                except ValueError:
                    source_id_int = None
                    target_id_int = None
                
                params = {
                    "source_id": source_id_int,
                    "source_name": source_id if not source_id_int else None,
                    "target_id": target_id_int,
                    "target_name": target_id if not target_id_int else None,
                    "props": rel_props
                }
                
                neo4j_client_instance.execute_write(query, params)
            except Exception as e:
                logger.warning(f"同步关系失败: {edge} - {e}")
        
        logger.info("图谱数据同步到 Neo4j 完成")
    except Exception as e:
        logger.error(f"同步图谱数据到 Neo4j 失败: {e}")
        raise


# 为前端添加的兼容API - 获取图谱数据
@app.get("/api/graph/data", tags=["知识图谱"])
async def get_graph_data(
    graph_id: Optional[str] = Query(None, description="图谱ID，如果指定则只返回该图谱的数据"),
    limit: Optional[int] = Query(None, ge=1, description="返回节点数量限制"),
    offset: Optional[int] = Query(None, ge=0, description="偏移量（用于分页）")
):
    """
    获取图谱数据（兼容前端API）
    优先从 Neo4j 读取数据，如果没有则从 MySQL 读取并同步到 Neo4j
    
    Args:
        graph_id: 图谱ID，如果指定则只返回该图谱的数据
        limit: 返回节点数量限制
        offset: 偏移量（用于分页）
    """
    try:
        all_nodes = []
        all_relations = []
        
        # 如果指定了 graph_id，只获取该图谱的数据
        if graph_id and mysql_client:
            graph_record = mysql_client.get_graph_by_id(graph_id)
            if not graph_record:
                return {
                    "nodes": [],
                    "edges": [],
                    "total_nodes": 0,
                    "total_relations": 0,
                    "status": "error",
                    "message": f"图谱 {graph_id} 不存在"
                }
            
            # 从 MySQL 读取该图谱的数据
            graph_data = graph_record.get("graph_data")
            
            # 处理 graph_data 可能为 None 的情况（旧记录可能没有这个字段）
            if graph_data is None:
                logger.warning(f"图谱 {graph_id} 没有 graph_data 数据，可能是在添加该字段之前创建的")
                # 如果 Neo4j 中有数据，尝试从 Neo4j 读取
                if neo4j_client:
                    try:
                        stats = neo4j_client.get_statistics()
                        if stats.get('nodes', 0) > 0:
                            logger.info("Neo4j 中有数据，从 Neo4j 读取...")
                            neo4j_data = neo4j_client.get_all_nodes_and_relationships(limit=limit, offset=offset)
                            all_nodes = neo4j_data.get('nodes', [])
                            all_relations = neo4j_data.get('relationships', [])
                            
                            # 应用分页
                            if limit is not None:
                                start_idx = offset or 0
                                end_idx = start_idx + limit
                                paginated_nodes = all_nodes[start_idx:end_idx]
                            else:
                                paginated_nodes = all_nodes
                            
                            # 只返回分页节点相关的边
                            paginated_node_ids = {node["id"] for node in paginated_nodes}
                            paginated_edges = []
                            for relation in all_relations:
                                source_id = str(relation.get("source", ""))
                                target_id = str(relation.get("target", ""))
                                if source_id in paginated_node_ids or target_id in paginated_node_ids:
                                    edge = {
                                        "id": relation.get("id", ""),
                                        "source": source_id,
                                        "target": target_id,
                                        "label": relation.get("label", relation.get("type", "")),
                                        "relation": relation.get("type", relation.get("label", "")),
                                        "properties": relation.get("properties", {})
                                    }
                                    paginated_edges.append(edge)
                            
                            return {
                                "nodes": paginated_nodes,
                                "edges": paginated_edges,
                                "total_nodes": len(all_nodes),
                                "total_relations": len(all_relations),
                                "status": "success",
                                "data": {
                                    "nodes": paginated_nodes,
                                    "edges": paginated_edges,
                                    "total_nodes": len(all_nodes),
                                    "total_relations": len(all_relations)
                                }
                            }
                    except Exception as e:
                        logger.warning(f"从 Neo4j 读取失败: {e}")
                
                # 如果 Neo4j 也没有数据，返回空数据
                return {
                    "nodes": [],
                    "edges": [],
                    "total_nodes": 0,
                    "total_relations": 0,
                    "status": "warning",
                    "message": f"图谱 {graph_id} 没有 graph_data 数据，且 Neo4j 中也没有数据"
                }
            
            # 解析 graph_data（可能是字符串或字典）
            if isinstance(graph_data, str):
                try:
                    graph_data = json.loads(graph_data)
                except json.JSONDecodeError:
                    logger.error(f"图谱 {graph_id} 的 graph_data 不是有效的 JSON")
                    graph_data = {}
            elif not isinstance(graph_data, dict):
                logger.warning(f"图谱 {graph_id} 的 graph_data 格式不正确: {type(graph_data)}")
                graph_data = {}
            
            # 确保 graph_data 是字典
            if not isinstance(graph_data, dict):
                graph_data = {}
            
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", graph_data.get("relations", []))
            
            # 当指定 graph_id 时，优先使用 MySQL 的数据（因为 MySQL 是按图谱分开存储的）
            # Neo4j 可能包含多个图谱的合并数据，不适合按 graph_id 过滤
            logger.info(f"使用 MySQL 中图谱 {graph_id} 的数据: {len(nodes)} 个节点, {len(edges)} 个关系")
            all_nodes = nodes
            all_relations = edges
            
            # 如果 Neo4j 中没有该图谱的数据，可以同步过去（但不会影响返回结果）
            if neo4j_client:
                try:
                    stats = neo4j_client.get_statistics()
                    if stats.get('nodes', 0) == 0:
                        logger.info("Neo4j 中没有数据，同步当前图谱数据到 Neo4j...")
                        sync_graph_data_to_neo4j(graph_data, neo4j_client)
                    else:
                        logger.debug("Neo4j 中已有数据，跳过同步（Neo4j 可能包含多个图谱的合并数据）")
                except Exception as e:
                    logger.warning(f"同步数据到 Neo4j 失败: {e}，但不影响返回结果")
        else:
            # 没有指定 graph_id，获取所有图谱数据
            # 优先从 Neo4j 读取数据
            if neo4j_client:
                try:
                    logger.info("从 Neo4j 读取知识图谱数据...")
                    neo4j_data = neo4j_client.get_all_nodes_and_relationships(limit=limit, offset=offset)
                    all_nodes = neo4j_data.get('nodes', [])
                    all_relations = neo4j_data.get('relationships', [])
                    
                    if all_nodes:
                        logger.info(f"从 Neo4j 成功获取 {len(all_nodes)} 个节点和 {len(all_relations)} 个关系")
                    else:
                        logger.info("Neo4j 中没有数据，尝试从 MySQL 读取...")
                except Exception as e:
                    logger.warning(f"从 Neo4j 读取数据失败: {e}，尝试从 MySQL 读取...")
            
            # 如果 Neo4j 没有数据或读取失败，从 MySQL 读取（备用方案）
            if not all_nodes and mysql_client:
                graphs = mysql_client.get_graphs()
                
                node_ids = set()
                relation_ids = set()
                
                # 合并所有知识图谱的节点和关系
                for gi, graph in enumerate(graphs):
                    graph_data = graph.get("graph_data")
                    
                    # 跳过没有 graph_data 的旧记录
                    if graph_data is None:
                        logger.debug(f"跳过图谱 {graph.get('graph_id', 'unknown')}：没有 graph_data 数据")
                        continue
                    
                    # 解析 graph_data（可能是字符串或字典）
                    if isinstance(graph_data, str):
                        try:
                            graph_data = json.loads(graph_data)
                        except json.JSONDecodeError:
                            logger.warning(f"图谱 {graph.get('graph_id', 'unknown')} 的 graph_data 不是有效的 JSON，跳过")
                            continue
                    elif not isinstance(graph_data, dict):
                        logger.warning(f"图谱 {graph.get('graph_id', 'unknown')} 的 graph_data 格式不正确: {type(graph_data)}，跳过")
                        continue
                    
                    nodes = graph_data.get("nodes", [])
                    edges = graph_data.get("edges", graph_data.get("relations", []))
                    
                    # 添加节点（去重）
                    for node in nodes:
                        if node["id"] not in node_ids:
                            node_ids.add(node["id"])
                            all_nodes.append(node)
                    
                    # 添加关系（去重）
                    for edge in edges:
                        edge_id = edge.get("id", f"{edge.get('source', '')}_{edge.get('target', '')}")
                        if edge_id not in relation_ids:
                            relation_ids.add(edge_id)
                            all_relations.append(edge)
                
                # 如果从 MySQL 读取到数据，同步到 Neo4j
                if all_nodes and neo4j_client:
                    try:
                        logger.info("将 MySQL 数据同步到 Neo4j...")
                        # 合并所有图谱数据
                        combined_graph_data = {
                            "nodes": all_nodes,
                            "edges": all_relations
                        }
                        sync_graph_data_to_neo4j(combined_graph_data, neo4j_client)
                    except Exception as e:
                        logger.warning(f"同步数据到 Neo4j 失败: {e}")
        
        # 应用分页（如果指定了 limit 和 offset）
        if limit is not None:
            start_idx = offset or 0
            end_idx = start_idx + limit
            paginated_nodes = all_nodes[start_idx:end_idx]
        else:
            paginated_nodes = all_nodes
        
        # 只返回分页节点相关的边
        paginated_node_ids = {node["id"] for node in paginated_nodes}
        paginated_edges = []
        for relation in all_relations:
            source_id = str(relation.get("source", ""))
            target_id = str(relation.get("target", ""))
            # 如果边的源节点或目标节点在分页节点中，则包含这条边
            if source_id in paginated_node_ids or target_id in paginated_node_ids:
                edge = {
                    "id": relation.get("id", ""),
                    "source": source_id,
                    "target": target_id,
                    "label": relation.get("label", relation.get("type", "")),
                    "relation": relation.get("type", relation.get("label", "")),
                    "properties": relation.get("properties", {})
                }
                paginated_edges.append(edge)
        
        # 返回前端期望的数据格式
        return {
            "nodes": paginated_nodes,
            "edges": paginated_edges,
            "total_nodes": len(all_nodes),
            "total_relations": len(all_relations),
            "status": "success",
            "data": {
                "nodes": paginated_nodes,
                "edges": paginated_edges,
                "total_nodes": len(all_nodes),
                "total_relations": len(all_relations)
            }
        }
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取图谱数据失败: {str(e)}")

# 为前端添加的兼容API - 获取实体详情
@app.get("/api/graph/entity/{entity_id}", tags=["知识图谱"])
async def get_entity_detail(entity_id: str):
    """
    获取实体详情（兼容前端API）
    """
    try:
        if not mysql_client:
            raise HTTPException(status_code=404, detail="实体不存在")
        
        entity = None
        entity_relations = []
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找指定ID的实体和相关关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            relations = graph_data.get("relations", [])
            
            # 查找实体
            for node in nodes:
                if node["id"] == entity_id:
                    entity = node
                    break
            
            # 查找与实体相关的关系
            for relation in relations:
                if relation["source"] == entity_id or relation["target"] == entity_id:
                    # 构建关系数据
                    if relation["source"] == entity_id:
                        relation_info = {
                            "id": relation["id"],
                            "target": relation["target"],
                            "label": relation["label"]
                        }
                    else:
                        relation_info = {
                            "id": relation["id"],
                            "source": relation["source"],
                            "label": relation["label"]
                        }
                    entity_relations.append(relation_info)
            
            # 如果找到了实体，提前退出循环
            if entity:
                break
        
        # 如果实体不存在
        if not entity:
            raise HTTPException(status_code=404, detail="实体不存在")
        
        # 构建完整的实体详情
        entity_detail = {
            "id": entity["id"],
            "label": entity["label"],
            "type": entity["type"],
            "properties": entity.get("properties", {}),
            "relations": entity_relations
        }
        
        return {
            "status": "success",
            "data": entity_detail
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实体详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取实体详情失败: {str(e)}")

# 为前端添加的兼容API - 获取关系详情
@app.get("/api/graph/relation/{relation_id}", tags=["知识图谱"])
async def get_relation_detail(relation_id: str):
    """
    获取关系详情（兼容前端API）
    """
    try:
        if not mysql_client:
            raise HTTPException(status_code=404, detail="关系不存在")
        
        relation = None
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找指定ID的关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            relations = graph_data.get("relations", [])
            
            # 查找关系
            for rel in relations:
                if rel["id"] == relation_id:
                    relation = rel
                    break
            
            # 如果找到了关系，提前退出循环
            if relation:
                break
        
        # 如果关系不存在
        if not relation:
            raise HTTPException(status_code=404, detail="关系不存在")
        
        return {
            "status": "success",
            "data": relation
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关系详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取关系详情失败: {str(e)}")

def _search_graph_entities(keyword: str = "", node_type: str = "") -> List[Dict[str, Any]]:
    """
    通用的实体搜索逻辑，供多个接口复用
    优先从 Neo4j 搜索（与图谱显示数据源一致），如果没有 Neo4j 则回退到 MySQL
    """
    logger.info(f"[search_entities] 开始搜索实体, keyword='{keyword}', type='{node_type}'")

    # 优先使用 Neo4j 搜索（与前端图谱显示的数据源一致）
    if neo4j_client:
        try:
            # 使用 Neo4j 的 search_entities 方法
            neo4j_results = neo4j_client.search_entities(
                keyword=keyword,
                node_type=node_type if node_type else None,
                limit=100
            )
            
            # 转换为前端期望的格式
            formatted_nodes = []
            for entity in neo4j_results:
                # Neo4j 返回的格式: {id, type, name, properties}
                # 转换为前端期望的格式: {id, name, type, category, ...}
                node = {
                    'id': entity.get('id', ''),
                    'name': entity.get('name', ''),
                    'type': entity.get('type', ''),
                    'category': entity.get('type', ''),  # type 和 category 都设为节点类型
                    'properties': entity.get('properties', {}),
                    'summary': entity.get('properties', {}).get('description', '') or entity.get('properties', {}).get('summary', ''),
                }
                formatted_nodes.append(node)
            
            logger.info(f"[search_entities] Neo4j搜索完成, 命中节点数={len(formatted_nodes)}")
            return formatted_nodes
            
        except Exception as e:
            logger.warning(f"Neo4j搜索失败: {e}，回退到MySQL搜索")
            # 继续执行下面的 MySQL 搜索逻辑

    # 回退到 MySQL 搜索（如果没有 Neo4j 或 Neo4j 搜索失败）
    if not mysql_client:
        logger.warning("[search_entities] MySQL客户端未初始化，返回空结果")
        return []

    all_nodes: List[Dict[str, Any]] = []
    node_ids: set = set()

    # 从数据库获取所有知识图谱数据
    graphs = mysql_client.get_graphs()

    # 查找匹配的实体
    for gi, graph in enumerate(graphs):
        graph_data = graph.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)

        nodes = graph_data.get("nodes", [])

        for ni, node in enumerate(nodes):
            if node["id"] in node_ids:
                continue

            # 将整个节点序列化成字符串，做一个"兜底"的模糊匹配
            try:
                import json as _json
                node_text = _json.dumps(node, ensure_ascii=False)
            except Exception:
                node_text = str(node)

            # 关键字匹配：节点整体文本中包含关键字即可
            match_keyword = (not keyword) or (keyword.lower() in node_text.lower())

            # 类型匹配
            match_type = not node_type or node_type == node.get("type")

            if match_keyword and match_type:
                node_ids.add(node["id"])
                all_nodes.append(node)

    logger.info(
        f"[search_entities] MySQL搜索完成, 图谱数={len(graphs)}, 命中节点数={len(all_nodes)}"
    )

    return all_nodes


# 为前端添加的兼容API - 原有图谱实体搜索接口
@app.get("/api/graph/entities/search", tags=["知识图谱"])
async def search_entities_legacy(keyword: Optional[str] = None, type: Optional[str] = None):
    """
    搜索图谱实体（兼容老的 /api/graph/entities/search，用于内部或调试）
    """
    try:
        keyword_str = keyword or ""
        type_str = type or ""
        all_nodes = _search_graph_entities(keyword_str, type_str)
        return {
            "status": "success",
            "data": {
                "list": all_nodes,
                "total": len(all_nodes),
            },
        }
    except Exception as e:
        logger.error(f"搜索实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索实体失败: {str(e)}")


# 新的实体搜索接口 - 提供给前端 SearchView.vue 使用
@app.get("/api/search/entities", tags=["搜索"])
async def search_entities(keyword: Optional[str] = None, type: Optional[str] = None, limit: int = 50):
    """
    实体搜索接口：
    - GET /api/search/entities?keyword=糖尿病&type=disease&limit=10
    - 返回 data: [entities...]，方便前端直接使用
    """
    try:
        keyword_str = keyword or ""
        type_str = type or ""
        all_nodes = _search_graph_entities(keyword_str, type_str)

        # 应用 limit
        if limit and limit > 0:
            all_nodes = all_nodes[:limit]

        return {
            "status": "success",
            "data": all_nodes,
        }
    except Exception as e:
        logger.error(f"实体搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"实体搜索失败: {str(e)}")

# 为前端添加的兼容API - 搜索图谱关系
@app.get("/api/graph/relations/search", tags=["知识图谱"])
async def search_relations(params: Optional[Dict[str, Any]] = None):
    """
    搜索图谱关系（兼容前端API）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 获取搜索参数
        keyword = params.get("keyword", "") if params else ""
        relation_label = params.get("label", "") if params else ""
        
        all_relations = []
        relation_ids = set()
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找匹配的关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            relations = graph_data.get("relations", [])
            
            for relation in relations:
                if relation["id"] not in relation_ids:
                    # 检查是否匹配搜索条件
                    match_keyword = not keyword or \
                                   keyword.lower() in relation["label"].lower() or \
                                   any(keyword.lower() in str(value).lower() for value in relation.get("properties", {}).values())
                    match_label = not relation_label or relation_label == relation["label"]
                    
                    if match_keyword and match_label:
                        relation_ids.add(relation["id"])
                        all_relations.append(relation)
        
        return {
            "status": "success",
            "data": {
                "list": all_relations,
                "total": len(all_relations)
            }
        }
    except Exception as e:
        logger.error(f"搜索关系失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索关系失败: {str(e)}")

# 为前端添加的兼容API - 扩展实体
@app.get("/api/graph/entity/{entity_id}/expand", tags=["知识图谱"])
async def expand_entity(entity_id: str, params: Optional[Dict[str, Any]] = None):
    """
    扩展实体（兼容前端API）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "nodes": [],
                    "relations": []
                }
            }
        
        expanded_nodes = []
        expanded_relations = []
        node_ids = set()
        relation_ids = set()
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找与指定实体相关的节点和关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            relations = graph_data.get("relations", [])
            
            # 查找与实体相关的关系
            for relation in relations:
                if relation["source"] == entity_id or relation["target"] == entity_id:
                    # 添加关系（去重）
                    if relation["id"] not in relation_ids:
                        relation_ids.add(relation["id"])
                        expanded_relations.append(relation)
                    
                    # 添加相关节点（去重）
                    if relation["source"] == entity_id:
                        # 添加目标节点
                        for node in nodes:
                            if node["id"] == relation["target"] and node["id"] not in node_ids:
                                node_ids.add(node["id"])
                                expanded_nodes.append(node)
                                break
                    else:
                        # 添加源节点
                        for node in nodes:
                            if node["id"] == relation["source"] and node["id"] not in node_ids:
                                node_ids.add(node["id"])
                                expanded_nodes.append(node)
                                break
        
        return {
            "status": "success",
            "data": {
                "nodes": expanded_nodes,
                "relations": expanded_relations
            }
        }
    except Exception as e:
        logger.error(f"扩展实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"扩展实体失败: {str(e)}")

# 搜索历史记录API
@app.get("/api/history/search", tags=["历史记录"])
async def search_history(keyword: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None):
    """
    搜索历史记录
    """
    try:
        if mysql_client:
            history_list = mysql_client.search_history_records(keyword, type, status)
        else:
            # 使用内存存储的历史记录进行搜索
            history_list = list(history_records.values())
            
            # 根据关键字过滤
            if keyword:
                keyword = keyword.lower()
                history_list = [
                    record for record in history_list 
                    if keyword in str(record.get('file_name', '')).lower() or 
                       keyword in str(record.get('message', '')).lower()
                ]
            
            # 根据类型过滤
            if type:
                history_list = [record for record in history_list if record.get('type') == type]
            
            # 根据状态过滤
            if status:
                history_list = [record for record in history_list if record.get('status') == status]
        
        return {
            "status": "success",
            "data": {
                "list": history_list,
                "total": len(history_list)
            }
        }
    except Exception as e:
        logger.error(f"搜索历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索历史记录失败: {str(e)}")


# 更新历史记录状态请求模型
class UpdateHistoryStatusRequest(BaseModel):
    """更新历史记录状态请求"""
    status: str = Field(..., description="新状态（如 'completed', 'failed', 'processing'）")
    message: Optional[str] = Field(None, description="状态消息")


# 更新历史记录状态API
@app.put("/api/history/{history_id}/status", tags=["历史记录"])
async def update_history_status(history_id: str, request: UpdateHistoryStatusRequest):
    """
    更新历史记录状态
    
    Args:
        history_id: 历史记录ID
        request: 包含 status 和 message 的请求体
    """
    try:
        status = request.status
        message = request.message or ""
        
        if mysql_client:
            # 如果使用 MySQL，尝试更新
            try:
                mysql_client.update_history_record_status(history_id, status)
                logger.info(f"历史记录状态已更新 (MySQL): {history_id} -> {status}")
                return {
                    "status": "success",
                    "message": "历史记录状态已更新"
                }
            except Exception as e:
                logger.warning(f"MySQL 更新历史记录状态失败: {e}，尝试内存存储")
        
        # 使用内存存储更新
        if history_id in history_records:
            history_records[history_id]["status"] = status
            if message:
                history_records[history_id]["message"] = message
            history_records[history_id]["updateTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"历史记录状态已更新 (内存): {history_id} -> {status}")
            return {
                "status": "success",
                "message": "历史记录状态已更新"
            }
        else:
            # 如果 history_id 不存在，返回成功（避免前端报错）
            logger.warning(f"历史记录不存在: {history_id}，但返回成功")
            return {
                "status": "success",
                "message": "历史记录状态已更新（记录不存在，但操作成功）"
            }
            
    except Exception as e:
        logger.error(f"更新历史记录状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新状态失败: {str(e)}")


# ==================== 智能问答接口 ====================

class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., description="用户问题", min_length=1, max_length=500)
    use_graph: bool = Field(True, description="是否使用图检索")
    use_vector: bool = Field(True, description="是否使用向量检索")
    top_k: int = Field(5, description="返回结果数量", ge=1, le=20)

    class Config:
        json_schema_extra = {
            "example": {
                "question": "什么是重症急性胰腺炎？",
                "use_graph": True,
                "use_vector": True,
                "top_k": 5
            }
        }


class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str = Field(..., description="原始问题")
    answer: str = Field(..., description="生成的答案")
    sources: List[Dict[str, Union[str, int, float, bool, None, List[Any], Dict[str, Any]]]] = Field(
        default_factory=list,
        description="信息来源"
    )
    confidence: float = Field(0.0, description="置信度", ge=0.0, le=1.0)
    processing_time: float = Field(..., description="处理时间（秒）")


@app.post("/api/query", response_model=QueryResponse, tags=["智能问答"])
async def query(request: QueryRequest):
    """
    处理用户查询（智能问答）
    
    - **question**: 用户问题
    - **use_graph**: 是否使用图检索（默认 True）
    - **use_vector**: 是否使用向量检索（默认 True）
    - **top_k**: 返回结果数量（默认 5）
    """
    start_time = time.time()
    
    try:
        logger.info(f"收到查询: {request.question}")
        
        # 检查 RAG 流水线是否可用
        if not rag_pipeline:
            raise HTTPException(
                status_code=503,
                detail="RAG 流水线未初始化，智能问答功能暂时不可用"
            )
        
        # 调用 RAG 流水线
        result = rag_pipeline.answer(
            query=request.question,
            use_graph=request.use_graph,
            use_vector=request.use_vector,
            top_k=request.top_k
        )
        
        processing_time = time.time() - start_time
        
        # 构建响应
        response = QueryResponse(
            question=request.question,
            answer=result.get("answer", "抱歉，我无法回答这个问题。"),
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            processing_time=processing_time
        )
        
        logger.info(f"查询完成，耗时: {processing_time:.2f}秒")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询处理失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询处理失败: {str(e)}")


# 启动应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )
