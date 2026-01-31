#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问答路由 - 提供 POST /api/query

与 Chat 前端兼容的请求/响应格式。
后续可在此处根据 USE_LEGACY_RAG 或 ?fallback=1 切换 Agent / 现有 RAG。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.query_service import run_query

router = APIRouter(prefix="/api", tags=["问答"])


class QueryRequest(BaseModel):
    """与 Chat 前端一致"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    max_results: int = Field(default=5, ge=1, le=20, description="最大返回结果数")


@router.post("/query")
async def api_query(req: QueryRequest):
    """
    智能问答。当前由 RAG 流水线实现；后续将切换为 LangGraph Agent，
    可通过 USE_LEGACY_RAG 或 ?fallback=1 使用本实现。
    """
    try:
        # 可选：USE_LEGACY_RAG 或 fallback 逻辑可在此扩展
        out = run_query(
            question=req.question,
            max_results=req.max_results,
            use_graph=True,
            use_vector=True,
        )
        if out.get("query_type") == "error" and out.get("error") and "暂不可用" in (out.get("answer") or ""):
            raise HTTPException(status_code=503, detail=out.get("answer", "服务不可用"))
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
