#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7.2 知识图谱构建任务状态

与 backend.app.tasks、/api/kg/build/progress、/api/hadoop/status 共用同一 tasks 数据源，
供 Agent Tool get_kg_build_status 调用。
"""

from typing import Any, Dict


def get_kg_build_status_impl(task_id: str) -> Dict[str, Any]:
    """
    查询知识图谱构建任务状态（含 /api/kg/build 单文件与 /api/hadoop/build/batch 批量任务）。

    Returns:
        {
            "found": bool,
            "status": str,       # processing | completed | failed | not_found
            "progress": int,
            "message": str,
            "current_chunk": int,
            "total_chunks": int,
            "entities_created": int,
            "relations_created": int,
            "current_processing": str,
            "file_id": str | None,
            "file_ids": list | None,
        }
    """
    try:
        import backend.app as app_module
        tasks = getattr(app_module, "tasks", {})
    except Exception:
        tasks = {}
    t = tasks.get(task_id) if tasks else None
    if not t:
        return {
            "found": False,
            "status": "not_found",
            "progress": 0,
            "message": "任务不存在",
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "current_processing": "",
            "file_id": None,
            "file_ids": None,
        }
    return {
        "found": True,
        "status": t.get("status", "unknown"),
        "progress": t.get("progress", 0),
        "message": t.get("message", ""),
        "current_chunk": t.get("current_chunk", 0),
        "total_chunks": t.get("total_chunks", 0),
        "entities_created": t.get("entities_created", 0),
        "relations_created": t.get("relations_created", 0),
        "current_processing": t.get("current_processing", ""),
        "file_id": t.get("file_id"),
        "file_ids": t.get("file_ids"),
    }
