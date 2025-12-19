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
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from db.mysql_client import get_mysql_client

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
logger.add(
    "logs/app.log",
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8"
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
        
        # 保存文件到本地
        file_path = os.path.join(UPLOAD_DIR, file_id)
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
            "path": file_path,
            "size": len(content),
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
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

# 后台知识图谱构建函数
def build_kg_background(task_id: str, file_id: str):
    """
    后台线程处理知识图谱构建任务
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
        file_content = file_info["content"]
        
        # 更新任务状态
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 10,
            "current_chunk": 1,
            "total_chunks": 1,
            "entities_created": 0,
            "relations_created": 0,
            "message": "正在准备处理文件...",
            "current_processing": "文件预处理",
            "file_id": file_id
        }
        
        # 模拟知识图谱构建过程
        # 实际项目中，这里应该调用知识图谱构建器
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 30,
            "current_chunk": 1,
            "total_chunks": 1,
            "entities_created": 0,
            "relations_created": 0,
            "message": "正在生成知识图谱...",
            "current_processing": "生成知识图谱",
            "file_id": file_id
        }
        
        # 生成模拟的知识图谱数据
        # 这里应该替换为实际的知识图谱生成逻辑
        entities_count = 10  # 模拟10个实体
        relations_count = 15  # 模拟15个关系
        
        # 更新任务状态
        tasks[task_id] = {
            "status": TaskStatus.COMPLETED,
            "progress": 100,
            "current_chunk": 1,
            "total_chunks": 1,
            "entities_created": entities_count,
            "relations_created": relations_count,
            "message": "知识图谱生成成功",
            "current_processing": "完成",
            "file_id": file_id
        }
        
        # 将知识图谱记录存储到MySQL
        if mysql_client:
            try:
                # 创建知识图谱记录
                graph_id = mysql_client.create_graph(
                    graph_name=filename,
                    description=f"从文件{filename}生成的知识图谱",
                    data_source=file_id,
                    file_path=file_id,
                    user_id="default_user"
                )
                
                # 更新图谱状态
                mysql_client.update_graph_status(
                    graph_id=graph_id,
                    status="completed",
                    entity_count=entities_count,
                    relation_count=relations_count
                )
                
                logger.info(f"知识图谱记录已存储到MySQL: {graph_id}")
            except Exception as e:
                logger.error(f"存储知识图谱记录到MySQL失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"知识图谱构建失败: {str(e)}")
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

# 为前端添加的兼容API - 获取图谱数据
@app.get("/api/graph/data", tags=["知识图谱"])
async def get_graph_data(params: Optional[Dict[str, Any]] = None):
    """
    获取图谱数据（兼容前端API）
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
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        all_nodes = []
        all_relations = []
        node_ids = set()
        relation_ids = set()
        
        # 合并所有知识图谱的节点和关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            relations = graph_data.get("relations", [])
            
            # 添加节点（去重）
            for node in nodes:
                if node["id"] not in node_ids:
                    node_ids.add(node["id"])
                    all_nodes.append(node)
            
            # 添加关系（去重）
            for relation in relations:
                if relation["id"] not in relation_ids:
                    relation_ids.add(relation["id"])
                    all_relations.append(relation)
        
        return {
            "status": "success",
            "data": {
                "nodes": all_nodes,
                "relations": all_relations,
                "total_nodes": len(all_nodes),
                "total_relations": len(all_relations)
            }
        }
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
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

# 为前端添加的兼容API - 搜索图谱实体
@app.get("/api/graph/entities/search", tags=["知识图谱"])
async def search_entities(params: Optional[Dict[str, Any]] = None):
    """
    搜索图谱实体（兼容前端API）
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
        node_type = params.get("type", "") if params else ""
        
        all_nodes = []
        node_ids = set()
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找匹配的实体
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            
            for node in nodes:
                if node["id"] not in node_ids:
                    # 检查是否匹配搜索条件
                    match_keyword = not keyword or keyword.lower() in node["label"].lower() or \
                                   any(keyword.lower() in str(value).lower() for value in node.get("properties", {}).values())
                    match_type = not node_type or node_type == node["type"]
                    
                    if match_keyword and match_type:
                        node_ids.add(node["id"])
                        all_nodes.append(node)
        
        return {
            "status": "success",
            "data": {
                "list": all_nodes,
                "total": len(all_nodes)
            }
        }
    except Exception as e:
        logger.error(f"搜索实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索实体失败: {str(e)}")

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
