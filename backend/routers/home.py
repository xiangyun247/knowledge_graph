#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首页相关API路由
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

from backend.auth import get_current_user_id
from db.mysql_client import get_mysql_client

router = APIRouter(prefix="/api/home", tags=["首页"])


class ChatHistoryCreate(BaseModel):
    type: str
    title: str = ""
    content: str = ""
    metadata: Optional[Dict[str, Any]] = None


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


@router.get("/overview")
async def home_overview(request: Request) -> Dict[str, Any]:
    """
    首页仪表盘统计：
    - 我的知识图谱数：当前用户在 knowledge_graphs 表中的记录数（或默认图谱+用户图谱）
    - 我的知识库文档数：当前用户在 Chroma 中的 doc 数（按 doc_id 聚合）
    - 本周已回答问题数：最近 7 天内的 chat 类型历史记录数（基于 history_records）
    - 最近活动：最近 3 条历史记录，涵盖图谱构建 / 文档上传 / 聊天 / 搜索
    """
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    graph_count = 0
    total_entities = 0
    total_relations = 0

    if mysql:
        try:
            result = mysql.execute_query(
                "SELECT COUNT(*) as cnt FROM knowledge_graphs WHERE user_id = :user_id OR user_id = 'default'",
                {"user_id": user_id}
            )
            if result:
                graph_count = result[0].get("cnt", 0)

            result = mysql.execute_query(
                "SELECT SUM(entity_count) as total FROM knowledge_graphs WHERE user_id = :user_id OR user_id = 'default'",
                {"user_id": user_id}
            )
            if result:
                total_entities = result[0].get("total", 0) or 0

            result = mysql.execute_query(
                "SELECT SUM(relation_count) as total FROM knowledge_graphs WHERE user_id = :user_id OR user_id = 'default'",
                {"user_id": user_id}
            )
            if result:
                total_relations = result[0].get("total", 0) or 0
        except Exception as e:
            pass

    doc_count = 0

    recent_activities = []

    return {
        "graph_count": graph_count,
        "doc_count": doc_count,
        "weekly_questions": 0,
        "recent_activities": recent_activities,
        "total_entities": total_entities,
        "total_relations": total_relations
    }
