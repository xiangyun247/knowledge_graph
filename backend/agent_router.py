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

from backend.auth import get_current_user_id, require_roles

logger = logging.getLogger(__name__)


# 统一错误码
E_OK = "E_OK"
E_MODEL = "E_MODEL"
E_AGENT = "E_AGENT"
E_PATIENT_EDU = "E_PATIENT_EDU"
E_TWEET = "E_TWEET"
E_INTERNAL = "E_INTERNAL"


def _error_detail(code: str, message: str) -> dict:
  """构造统一的错误返回体 detail 字段。"""
  return {"code": code, "message": message}


def _log_api_event(user_id: str, api: str, status: str, elapsed: float, **extra):
  """统一结构化日志，便于后续分析。"""
  payload = {
    "api": api,
    "status": status,
    "elapsed_ms": int(elapsed * 1000),
    "user_id": user_id or "",
  }
  payload.update(extra or {})
  try:
    logger.info(json.dumps(payload, ensure_ascii=False))
  except Exception:
    logger.info(payload)

router = APIRouter(prefix="/api", tags=["Agent"])


@router.get("/llm/models")
async def api_llm_models():
    """
    返回全部 LLM 模型列表（含未配置），每项带 configured: bool。
    未配置的模型也会出现在选项中；前端在选用未配置模型时提示「未配置该模型」。
    """
    try:
        from llm.models_config import get_all_models, get_default_model_id
        models = get_all_models()
        default = get_default_model_id()
        return {"data": models, "default": default}
    except Exception as e:
        logger.warning("获取 LLM 模型列表失败: %s", e)
        return {"data": [], "default": "deepseek-chat"}


class AgentQueryRequest(BaseModel):
    """Agent 问答请求，与 Chat 前端兼容"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")
    session_id: Optional[str] = Field(None, description="会话 id，6.1 用于多轮对话记忆")
    model: Optional[str] = Field(None, description="多 LLM 支持：模型 id，如 deepseek-chat、qwen-plus，需在 .env 配置 API Key")
    deep_think: bool = Field(False, description="是否返回「深度思考」分析 trace")
    intent: Optional[str] = Field(None, description="意图：patient_education/science_tweet 时直接生成对应内容")


class ScienceTweetRequest(BaseModel):
    """科普推文生成请求（用于「推文版」按钮）"""
    topic: str = Field(..., min_length=1, max_length=300, description="主题")
    source_content: Optional[str] = Field(None, description="已有回答内容，作为参考提炼推文")
    word_limit: int = Field(140, ge=80, le=500, description="每条字数限制")
    style: str = Field("轻松", description="风格：轻松/严谨/亲切")


@router.post("/science-tweet", dependencies=[require_roles("admin", "doctor", "patient")])
async def api_science_tweet(request: Request, req: ScienceTweetRequest):
    """
    生成科普推文。用于「推文版」按钮：将已有问答转化为 1～3 条推文。
    传入 topic（原问题）和可选的 source_content（已有回答），基于 RAG 或已有内容生成推文。
    """
    user_id = get_current_user_id(request)
    try:
        from backend.agent.science_tweet import generate_science_tweet
        from backend.agent.context import set_agent_user_id
        set_agent_user_id(user_id)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: generate_science_tweet(
                topic=req.topic.strip(),
                word_limit=req.word_limit,
                style=req.style.strip() or "轻松",
                source_content=req.source_content.strip() if req.source_content else None,
            ),
        )
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        return {"data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("科普推文生成失败")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.post("/agent/query", dependencies=[require_roles("admin", "doctor", "patient")])
async def api_agent_query(request: Request, req: AgentQueryRequest):
    """
    使用 LangGraph Agent 进行问答。
    6.1 若提供 session_id，从 Redis/内存 取历史并拼进上下文；答后回写。
    7.1 传入 user_id 供 tools 做文档/图谱权限过滤。
    返回: answer, sources, response, question, processing_time
    """
    api_path = "/api/agent/query"
    start = time.time()
    try:
        from backend.agent import run_agent
        from backend.agent_session import get_session_history, append_session_exchange
    except Exception as e:
        err = str(e)[:280]
        logger.warning("Agent 模块导入失败: %s", e)
        elapsed = time.time() - start
        _log_api_event(
          user_id="",
          api=api_path,
          status="error",
          elapsed=elapsed,
          error=str(e),
          code=E_AGENT,
        )
        raise HTTPException(
            status_code=503,
            detail=_error_detail(E_AGENT, f"Agent 服务暂不可用，请检查 DEEPSEEK_API_KEY 及依赖（langgraph、langchain-openai 等）。错误: {err}"),
        )

    user_id = get_current_user_id(request)

    # intent=science_tweet：直接生成科普推文
    if (req.intent or "").strip().lower() == "science_tweet":
        try:
            from backend.agent.science_tweet import generate_science_tweet
            from backend.agent.context import set_agent_user_id
            from backend.agent_session import append_session_exchange
            set_agent_user_id(user_id)
            start = time.time()
            loop = asyncio.get_event_loop()
            st_result = await loop.run_in_executor(
                None,
                lambda: generate_science_tweet(topic=req.question.strip(), word_limit=140, style="轻松"),
            )
            elapsed = time.time() - start
            if st_result.get("error"):
                answer = f"[科普推文生成失败] {st_result.get('error')}"
                st_result = None
            else:
                lines = []
                for i, t in enumerate(st_result.get("tweets") or [], 1):
                    lines.append(f"推文 {i}：{t}")
                tags = st_result.get("hashtags") or []
                if tags:
                    lines.append(f"\n话题标签建议：{' '.join(tags)}")
                answer = "\n".join(lines)
            if req.session_id and req.session_id.strip():
                append_session_exchange(req.session_id, req.question, answer)
            _log_api_event(
              user_id=user_id,
              api=api_path,
              status="ok",
              elapsed=elapsed,
              mode="science_tweet",
              model=req.model or "",
            )
            return {
                "question": req.question,
                "answer": answer,
                "response": answer,
                "sources": [],
                "trace": None,
                "processing_time": round(elapsed, 3),
                "science_tweet": st_result,
            }
        except Exception as e:
            logger.exception("科普推文生成失败")
            elapsed = time.time() - start
            _log_api_event(
              user_id=user_id,
              api=api_path,
              status="error",
              elapsed=elapsed,
              mode="science_tweet",
              model=req.model or "",
              error=str(e),
              code=E_TWEET,
            )
            raise HTTPException(status_code=500, detail=_error_detail(E_TWEET, str(e)))

    # intent=patient_education：直接调用患者教育生成，返回结构化内容
    if (req.intent or "").strip().lower() == "patient_education":
        try:
            from backend.agent.patient_education import generate_patient_education
            from backend.agent.context import set_agent_user_id
            from backend.agent_session import append_session_exchange
            set_agent_user_id(user_id)
            start = time.time()
            loop = asyncio.get_event_loop()
            pe_result = await loop.run_in_executor(
                None,
                lambda: generate_patient_education(topic=req.question.strip()),
            )
            elapsed = time.time() - start
            if pe_result.get("error"):
                answer = f"[患者教育生成失败] {pe_result.get('error')}"
                pe_result = None
            else:
                lines = [f"# {pe_result.get('title', req.question)}", ""]
                for sec in pe_result.get("sections") or []:
                    lines.append(f"## {sec.get('heading', '')}")
                    lines.append(sec.get("content", ""))
                    lines.append("")
                if pe_result.get("summary"):
                    lines.append(f"**温馨提示**：{pe_result.get('summary')}")
                answer = "\n".join(lines)
            if req.session_id and req.session_id.strip():
                append_session_exchange(req.session_id, req.question, answer)
            _log_api_event(
              user_id=user_id,
              api=api_path,
              status="ok",
              elapsed=elapsed,
              mode="patient_education",
              model=req.model or "",
            )
            return {
                "question": req.question,
                "answer": answer,
                "response": answer,
                "sources": [],
                "trace": None,
                "processing_time": round(elapsed, 3),
                "patient_education": pe_result,
            }
        except Exception as e:
            logger.exception("患者教育生成失败")
            elapsed = time.time() - start
            _log_api_event(
              user_id=user_id,
              api=api_path,
              status="error",
              elapsed=elapsed,
              mode="patient_education",
              model=req.model or "",
              error=str(e),
              code=E_PATIENT_EDU,
            )
            raise HTTPException(status_code=500, detail=_error_detail(E_PATIENT_EDU, str(e)))

    initial_messages = None
    if req.session_id and req.session_id.strip():
        hist = get_session_history(req.session_id)
        initial_messages = _history_to_messages(hist)

    if req.model:
        try:
            from llm.models_config import get_llm_config
            if get_llm_config(req.model) is None:
                raise HTTPException(status_code=400, detail="未配置该模型")
        except HTTPException:
            raise

    start = time.time()
    try:
        loop = asyncio.get_event_loop()
        out = await loop.run_in_executor(
            None,
            lambda: run_agent(
                req.question,
                initial_messages=initial_messages,
                user_id=user_id,
                model_id=req.model,
                deep_think=req.deep_think,
            ),
        )
    except Exception as e:
        logger.exception("run_agent 执行失败")
        elapsed = time.time() - start
        _log_api_event(
          user_id=user_id,
          api=api_path,
          status="error",
          elapsed=elapsed,
          mode="agent",
          model=req.model or "",
          error=str(e),
          code=E_AGENT,
        )
        raise HTTPException(status_code=500, detail=_error_detail(E_AGENT, str(e)))

    elapsed = time.time() - start
    answer = out.get("answer", "")

    if req.session_id and req.session_id.strip():
        append_session_exchange(req.session_id, req.question, answer)

    _log_api_event(
      user_id=user_id,
      api=api_path,
      status="ok",
      elapsed=elapsed,
      mode="agent",
      model=req.model or "",
    )
    return {
        "question": req.question,
        "answer": answer,
        "response": answer,
        "sources": out.get("sources", []),
        "trace": out.get("trace"),
        "processing_time": round(elapsed, 3),
    }


@router.post("/agent/query/stream", dependencies=[require_roles("admin", "doctor", "patient")])
async def api_agent_query_stream(request: Request, req: AgentQueryRequest):
    """
    6.2 流式问答：SSE 推送 chunk（打字机）与 done（answer+sources）。
    7.1 传入 user_id 供 tools 做文档/图谱权限过滤。
    intent=patient_education 时直接生成患者教育，一次性返回 done。
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

    # intent=science_tweet：直接生成科普推文
    if (req.intent or "").strip().lower() == "science_tweet":
        try:
            from backend.agent.science_tweet import generate_science_tweet
            from backend.agent.context import set_agent_user_id
            set_agent_user_id(user_id)
            loop = asyncio.get_event_loop()
            st_result = await loop.run_in_executor(
                None,
                lambda: generate_science_tweet(topic=req.question.strip(), word_limit=140, style="轻松"),
            )
            if st_result.get("error"):
                answer = f"[科普推文生成失败] {st_result.get('error')}"
                st_result = None
            else:
                lines = []
                for i, t in enumerate(st_result.get("tweets") or [], 1):
                    lines.append(f"推文 {i}：{t}")
                tags = st_result.get("hashtags") or []
                if tags:
                    lines.append(f"\n话题标签建议：{' '.join(tags)}")
                answer = "\n".join(lines)
            if req.session_id and req.session_id.strip():
                append_session_exchange(req.session_id, req.question, answer)

            def event_gen():
                yield f"data: {json.dumps({'type': 'done', 'answer': answer, 'sources': [], 'science_tweet': st_result}, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                event_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        except Exception as e:
            logger.exception("科普推文生成失败")
            raise HTTPException(status_code=500, detail=str(e))

    # intent=patient_education：直接生成，一次性返回
    if (req.intent or "").strip().lower() == "patient_education":
        try:
            from backend.agent.patient_education import generate_patient_education
            from backend.agent.context import set_agent_user_id
            set_agent_user_id(user_id)
            loop = asyncio.get_event_loop()
            pe_result = await loop.run_in_executor(
                None,
                lambda: generate_patient_education(topic=req.question.strip()),
            )
            if pe_result.get("error"):
                answer = f"[患者教育生成失败] {pe_result.get('error')}"
                pe_result = None
            else:
                lines = [f"# {pe_result.get('title', req.question)}", ""]
                for sec in pe_result.get("sections") or []:
                    lines.append(f"## {sec.get('heading', '')}")
                    lines.append(sec.get("content", ""))
                    lines.append("")
                if pe_result.get("summary"):
                    lines.append(f"**温馨提示**：{pe_result.get('summary')}")
                answer = "\n".join(lines)
            if req.session_id and req.session_id.strip():
                append_session_exchange(req.session_id, req.question, answer)

            def event_gen():
                yield f"data: {json.dumps({'type': 'done', 'answer': answer, 'sources': [], 'patient_education': pe_result}, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                event_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        except Exception as e:
            logger.exception("患者教育生成失败")
            raise HTTPException(status_code=500, detail=str(e))

    initial_messages = None
    if req.session_id and req.session_id.strip():
        hist = get_session_history(req.session_id)
        initial_messages = _history_to_messages(hist)

    if req.model:
        try:
            from llm.models_config import get_llm_config
            if get_llm_config(req.model) is None:
                raise HTTPException(status_code=400, detail="未配置该模型")
        except HTTPException:
            raise

    def event_gen():
        try:
            for ev in run_agent_stream(
                req.question,
                initial_messages=initial_messages,
                user_id=user_id,
                model_id=req.model,
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
