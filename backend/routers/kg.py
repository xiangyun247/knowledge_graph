#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱API路由
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.auth import get_current_user_id, require_roles
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


class BuildKGFromFileRequest(BaseModel):
    file_id: str
    file_name: str
    use_hadoop: bool = False
    description: Optional[str] = None


@router.get("/list")
async def get_kg_list():
    """获取知识图谱列表"""
    mysql = get_mysql()
    try:
        if mysql:
            result = mysql.execute_query(
                """SELECT graph_id, graph_name, description, entity_count, relation_count, created_at
                   FROM knowledge_graphs ORDER BY created_at DESC"""
            )
            formatted = []
            for row in (result or []):
                formatted.append({
                    "id": row.get("graph_id"),
                    "name": row.get("graph_name"),
                    "description": row.get("description"),
                    "node_count": row.get("entity_count", 0),
                    "edge_count": row.get("relation_count", 0),
                    "created_at": row.get("created_at")
                })
            return {"status": "success", "data": formatted}
        return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"获取图谱列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{graph_id}")
async def get_kg_detail(graph_id: str):
    """获取知识图谱详情"""
    mysql = get_mysql()
    try:
        if mysql:
            result = mysql.execute_query(
                "SELECT * FROM knowledge_graphs WHERE graph_id = :id",
                {"id": graph_id}
            )
            if result:
                return {"status": "success", "data": result[0]}
        raise HTTPException(status_code=404, detail="图谱不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图谱详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{graph_id}/visualize")
async def get_kg_visualize_data(graph_id: str):
    """获取图谱可视化数据"""
    mysql = get_mysql()
    try:
        if mysql:
            result = mysql.execute_query(
                "SELECT graph_data FROM knowledge_graphs WHERE graph_id = :id",
                {"id": graph_id}
            )
            if result and result[0].get("graph_data"):
                import json
                graph_data = json.loads(result[0]["graph_data"])
                return {"status": "success", "data": graph_data}
        raise HTTPException(status_code=404, detail="图谱不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{graph_id}/nodes")
async def get_kg_nodes(graph_id: str):
    """获取图谱节点列表"""
    mysql = get_mysql()
    try:
        if mysql:
            result = mysql.execute_query(
                "SELECT * FROM kg_nodes WHERE graph_id = :graph_id",
                {"graph_id": graph_id}
            )
            return {"status": "success", "data": result or []}
        return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"获取节点列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{graph_id}/relations")
async def get_kg_relations(graph_id: str):
    """获取图谱关系列表"""
    mysql = get_mysql()
    try:
        if mysql:
            result = mysql.execute_query(
                "SELECT * FROM kg_relations WHERE graph_id = :graph_id",
                {"graph_id": graph_id}
            )
            return {"status": "success", "data": result or []}
        return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"获取关系列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
