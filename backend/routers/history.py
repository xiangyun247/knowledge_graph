#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史记录API路由
"""

import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Body
from pydantic import BaseModel

from backend.auth import get_current_user_id, require_roles
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/history", tags=["历史记录"])


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


history_records: Dict[str, Dict[str, Any]] = {}
history_counter = 0


@router.get("/list")
async def get_history_list(
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    获取历史记录列表，最多返回 limit 条（默认 1000）。
    """
    mysql = get_mysql()

    try:
        history_list: List[Dict[str, Any]] = []

        if mysql:
            history_list = mysql.get_histories(limit=limit, offset=offset)
        else:
            history_list = list(history_records.values())

        if type:
            history_list = [record for record in history_list if record.get("type") == type]

        if status:
            history_list = [record for record in history_list if record.get("status") == status]

        if not mysql:
            history_list.sort(key=lambda r: r.get("created_at") or r.get("createTime") or "", reverse=True)
            history_list = history_list[offset : offset + limit]

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


@router.get("/stats")
async def get_history_stats():
    """获取历史记录统计信息"""
    mysql = get_mysql()
    try:
        if mysql:
            stats = mysql.get_history_stats()
            return {"status": "success", "data": stats}
        else:
            return {"status": "error", "message": "MySQL客户端未初始化"}
    except Exception as e:
        logger.error(f"获取历史记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史记录统计失败: {str(e)}")


@router.post("/save")
async def save_history(request: Request, record: ChatHistoryCreate):
    """保存聊天/图谱/上传等历史记录"""
    global history_counter
    mysql = get_mysql()

    try:
        user_id = get_current_user_id(request)
        if not user_id:
            user_id = "anonymous"

        record_id = str(uuid.uuid4())
        now = ""

        if mysql:
            try:
                mysql.execute_update(
                    """INSERT INTO chat_history (user_id, type, title, content, metadata, status)
                       VALUES (:user_id, :type, :title, :content, :metadata, 'active')""",
                    {
                        "user_id": user_id,
                        "type": record.type,
                        "title": record.title,
                        "content": record.content,
                        "metadata": str(record.metadata) if record.metadata else None
                    }
                )
            except Exception as e:
                logger.warning(f"MySQL保存历史记录失败: {e}")

        history_records[record_id] = {
            "id": record_id,
            "userId": user_id,
            "type": record.type,
            "title": record.title,
            "content": record.content,
            "metadata": record.metadata or {},
            "status": "active",
            "created_at": now
        }

        return {"status": "success", "id": record_id}
    except Exception as e:
        logger.error(f"保存历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存历史记录失败: {str(e)}")


@router.put("/{history_id}/status")
async def update_history_status(history_id: str, body: Optional[dict] = Body(None)):
    """更新历史记录状态"""
    mysql = get_mysql()

    if mysql:
        try:
            mysql.execute_update(
                "UPDATE chat_history SET status = :status WHERE id = :id",
                {"id": history_id, "status": body.get("status") if body else "inactive"}
            )
        except Exception as e:
            logger.warning(f"MySQL更新历史记录状态失败: {e}")

    if history_id in history_records:
        if body and body.get("status"):
            history_records[history_id]["status"] = body.get("status")

    return {"status": "success"}


@router.delete("/clear")
async def clear_history_all(request: Request):
    """清空所有历史记录"""
    mysql = get_mysql()
    user_id = get_current_user_id(request)

    if mysql:
        try:
            mysql.execute_update(
                "UPDATE chat_history SET status = 'inactive' WHERE user_id = :user_id",
                {"user_id": user_id}
            )
        except Exception as e:
            logger.warning(f"MySQL清空历史记录失败: {e}")

    global history_records
    history_records = {}

    return {"status": "success"}


@router.delete("/{history_id}")
async def delete_history_one(history_id: str):
    """删除单条历史记录"""
    mysql = get_mysql()

    if mysql:
        try:
            mysql.execute_update(
                "UPDATE chat_history SET status = 'deleted' WHERE id = :id",
                {"id": history_id}
            )
        except Exception as e:
            logger.warning(f"MySQL删除历史记录失败: {e}")

    if history_id in history_records:
        del history_records[history_id]

    return {"status": "success"}


class BatchDeleteHistoryBody(BaseModel):
    ids: List[str]


@router.post("/batch-delete")
async def batch_delete_history(body: BatchDeleteHistoryBody):
    """批量删除历史记录"""
    mysql = get_mysql()

    if not body.ids:
        raise HTTPException(status_code=400, detail="IDs不能为空")

    if mysql:
        try:
            placeholders = ",".join([f":id{i}" for i in range(len(body.ids))])
            params = {f"id{i}": id for i, id in enumerate(body.ids)}
            mysql.execute_update(
                f"UPDATE chat_history SET status = 'deleted' WHERE id IN ({placeholders})",
                params
            )
        except Exception as e:
            logger.warning(f"MySQL批量删除历史记录失败: {e}")

    for id in body.ids:
        if id in history_records:
            del history_records[id]

    return {"status": "success", "count": len(body.ids)}
