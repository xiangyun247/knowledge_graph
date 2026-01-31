#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问答服务 - 为 /api/query 提供 RAG 能力

在 backend 中复用 rag.rag_pipeline，供 query_router 调用。
后续将由此处切换为 LangGraph Agent（USE_LEGACY_RAG 时保留当前 RAG）。
"""

import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_rag: Optional[Any] = None
_initialized: bool = False
_init_error: Optional[str] = None


def init() -> bool:
    """初始化 RAG 流水线。成功返回 True，失败返回 False 并记录 _init_error。"""
    global _rag, _initialized, _init_error

    if _initialized:
        return _rag is not None

    _initialized = True

    try:
        import config
        from db.neo4j_client import Neo4jClient
        from llm.client import LLMClient, EmbeddingClient
        from rag.rag_pipeline import RAGPipeline

        # Neo4j
        nc = Neo4jClient()
        if not nc.verify_connection():
            raise RuntimeError("Neo4j 连接验证失败")

        # LLM（DeepSeek）
        ak = getattr(config, "DEEPSEEK_API_KEY", None) or os.getenv("DEEPSEEK_API_KEY")
        if not ak:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，LLM 功能不可用")
        lc = LLMClient(
            api_key=ak,
            base_url=getattr(config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=getattr(config, "DEEPSEEK_MODEL", "deepseek-chat"),
        )

        # Embedding
        ec = EmbeddingClient()

        _rag = RAGPipeline(neo4j_client=nc, llm_client=lc, embedding_client=ec)
        logger.info("query_service: RAG 流水线初始化成功")
        return True

    except Exception as e:
        _init_error = str(e)
        logger.exception("query_service: RAG 流水线初始化失败")
        return False


def run_query(
    question: str,
    max_results: int = 5,
    use_graph: bool = True,
    use_vector: bool = True,
) -> Dict[str, Any]:
    """
    执行问答。优先使用 RAG；若未初始化则尝试 init，仍不可用则返回降级结果。

    返回结构与 Chat 前端兼容：answer, response, sources, question, query_type 等。
    """
    global _rag, _initialized, _init_error

    if _rag is None and not _initialized:
        init()

    if _rag is None:
        msg = "问答服务暂不可用，请检查配置（Neo4j、DEEPSEEK_API_KEY 等）后重试。"
        if _init_error:
            msg += f" 详情: {_init_error}"
        return {
            "question": question,
            "answer": msg,
            "response": msg,
            "sources": [],
            "query_type": "error",
            "error": _init_error,
        }

    try:
        res = _rag.answer(
            query=question,
            use_graph=use_graph,
            use_vector=use_vector,
            top_k=max_results,
        )
        # 与 ChatView 兼容：answer、response、sources
        answer = res.get("answer") or ""
        meta = res.get("metadata") or {}
        return {
            "question": res.get("query", question),
            "answer": answer,
            "response": answer,
            "sources": res.get("sources", []),
            "confidence": res.get("confidence", 0.0),
            "processing_time": res.get("processing_time", 0.0),
            "query_type": meta.get("parsed_intent", "rag"),
        }
    except Exception as e:
        logger.exception("run_query 执行失败")
        fallback = "抱歉，处理您的问题时遇到了错误，请稍后重试。"
        return {
            "question": question,
            "answer": fallback,
            "response": fallback,
            "sources": [],
            "query_type": "error",
            "error": str(e),
        }
