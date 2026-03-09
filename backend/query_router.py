#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问答路由 - 提供 POST /api/query

与 Chat 前端兼容的请求/响应格式。
后续可在此处根据 USE_LEGACY_RAG 或 ?fallback=1 切换 Agent / 现有 RAG。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth import get_current_user_id
from backend.query_service import run_query

router = APIRouter(prefix="/api", tags=["问答"])


class QueryRequest(BaseModel):
    """与 Chat 前端一致"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    max_results: int = Field(default=5, ge=1, le=20, description="最大返回结果数")
    use_hybrid: bool = Field(default=False, description="启用 Hybrid RAG 混合检索（图+Chroma+关键词 RRF 融合）")


@router.post("/query")
async def api_query(req: QueryRequest, request: Request):
    """
    智能问答。当前由 RAG 流水线实现；后续将切换为 LangGraph Agent，
    可通过 USE_LEGACY_RAG 或 ?fallback=1 使用本实现。
    use_hybrid=True 时使用 Hybrid RAG（图+Chroma+关键词 RRF 融合），user_id 从请求头/Token 获取用于 Chroma 过滤。
    """
    try:
        user_id = get_current_user_id(request)
        out = run_query(
            question=req.question,
            max_results=req.max_results,
            use_graph=True,
            use_vector=True,
            use_hybrid=req.use_hybrid,
            user_id=user_id or None,
        )
        if out.get("query_type") == "error" and out.get("error") and "暂不可用" in (out.get("answer") or ""):
            raise HTTPException(status_code=503, detail=out.get("answer", "服务不可用"))
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
