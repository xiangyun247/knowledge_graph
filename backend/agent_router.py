#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5.1 / 6.1 Agent 问答 HTTP 接口

POST /api/agent/query：入参 question、可选 session_id；
6.1 按 session_id 取历史、拼进 LLM 上下文，支持多轮、指代、追问；答后回写会话。
6.2 POST /api/agent/query/stream：SSE 流式返回（打字机式）。
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Agent"])


class AgentQueryRequest(BaseModel):
    """Agent 问答请求，与 Chat 前端兼容"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    session_id: Optional[str] = Field(None, description="会话 id，6.1 用于多轮对话记忆")
    deep_think: bool = Field(False, description="是否返回「深度思考」分析 trace")


def _history_to_messages(history: list):
    """将 agent_session 的 [{role,content}] 转为 [HumanMessage, AIMessage, ...]。"""
    from langchain_core.messages import AIMessage, HumanMessage
    out = []
    for h in (history or []):
        role = (h.get("role") or "").strip().lower()
        c = h.get("content") or ""
        if role == "user":
            out.append(HumanMessage(content=c))
        elif role == "assistant":
            out.append(AIMessage(content=c))
    return out


@router.post("/agent/query")
async def api_agent_query(request: Request, req: AgentQueryRequest):
    """
    使用 LangGraph Agent 进行问答。
    6.1 若提供 session_id，从 Redis/内存 取历史并拼进上下文；答后回写。
    7.1 传入 user_id 供 tools 做文档/图谱权限过滤。
    返回: answer, sources, response, question, processing_time
    """
    try:
        from backend.agent import run_agent
        from backend.agent_session import get_session_history, append_session_exchange
    except Exception as e:
        err = str(e)[:280]
        logger.warning("Agent 模块导入失败: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Agent 服务暂不可用，请检查 DEEPSEEK_API_KEY 及依赖（langgraph、langchain-openai 等）。错误: {err}",
        )

    user_id = get_current_user_id(request)
    initial_messages = None
    if req.session_id and req.session_id.strip():
        hist = get_session_history(req.session_id)
        initial_messages = _history_to_messages(hist)

    start = time.time()
    try:
        loop = asyncio.get_event_loop()
        out = await loop.run_in_executor(
            None,
            lambda: run_agent(
                req.question,
                initial_messages=initial_messages,
                user_id=user_id,
                deep_think=req.deep_think,
            ),
        )
    except Exception as e:
        logger.exception("run_agent 执行失败")
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - start
    answer = out.get("answer", "")

    if req.session_id and req.session_id.strip():
        append_session_exchange(req.session_id, req.question, answer)

    return {
        "question": req.question,
        "answer": answer,
        "response": answer,
        "sources": out.get("sources", []),
        "trace": out.get("trace"),
        "processing_time": round(elapsed, 3),
    }


@router.post("/agent/query/stream")
async def api_agent_query_stream(request: Request, req: AgentQueryRequest):
    """
    6.2 流式问答：SSE 推送 chunk（打字机）与 done（answer+sources）。
    7.1 传入 user_id 供 tools 做文档/图谱权限过滤。
    """
    try:
        from backend.agent import run_agent_stream
        from backend.agent_session import get_session_history, append_session_exchange
    except Exception as e:
        err = str(e)[:280]
        logger.warning("Agent 模块导入失败: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Agent 服务暂不可用。错误: {err}",
        )

    user_id = get_current_user_id(request)
    initial_messages = None
    if req.session_id and req.session_id.strip():
        hist = get_session_history(req.session_id)
        initial_messages = _history_to_messages(hist)

    def event_gen():
        try:
            for ev in run_agent_stream(
                req.question,
                initial_messages=initial_messages,
                user_id=user_id,
                deep_think=req.deep_think,
            ):
                if ev.get("type") == "done" and req.session_id and req.session_id.strip():
                    append_session_exchange(req.session_id, req.question, ev.get("answer", ""))
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("run_agent_stream 失败")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
