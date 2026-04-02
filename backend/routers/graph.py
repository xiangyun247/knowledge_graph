#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图谱API路由
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from backend.auth import get_current_user_id, require_roles
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/graph", tags=["知识图谱"])


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


@router.get("/list")
async def get_graph_list(request: Request):
    """获取图谱列表"""
    mysql = get_mysql()
    user_id = get_current_user_id(request)

    try:
        if mysql:
            result = mysql.execute_query(
                """SELECT id, name, description, node_count, edge_count, created_at
                   FROM knowledge_graphs
                   WHERE user_id = :user_id OR user_id = 'default'
                   ORDER BY created_at DESC""",
                {"user_id": user_id}
            )
            return {"status": "success", "data": result or []}
        return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"获取图谱列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_graph_all(request: Request):
    """清空所有图谱"""
    mysql = get_mysql()
    user_id = get_current_user_id(request)

    if mysql:
        try:
            mysql.execute_update(
                "DELETE FROM knowledge_graphs WHERE user_id = :user_id AND user_id != 'default'",
                {"user_id": user_id}
            )
        except Exception as e:
            logger.warning(f"MySQL清空图谱失败: {e}")

    return {"status": "success"}


@router.delete("/{graph_id}")
async def delete_graph_one(request: Request, graph_id: str):
    """删除单个图谱"""
    mysql = get_mysql()
    user_id = get_current_user_id(request)

    if mysql:
        try:
            mysql.execute_update(
                "DELETE FROM knowledge_graphs WHERE id = :id AND user_id = :user_id",
                {"id": graph_id, "user_id": user_id}
            )
        except Exception as e:
            logger.warning(f"MySQL删除图谱失败: {e}")

    return {"status": "success"}
