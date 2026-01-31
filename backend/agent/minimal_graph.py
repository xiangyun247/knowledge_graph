#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4.1 最小 LangGraph 图：开始 → LLM → 结束

在不动现有 RAG 的前提下，验证 LangGraph + DeepSeek 可跑通。
"""

import os
import logging
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


class MinimalState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def _get_llm() -> ChatOpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY") or getattr(
        __import__("config", fromlist=["DEEPSEEK_API_KEY"]),
        "DEEPSEEK_API_KEY",
        None,
    )
    base = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    model = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        base_url=base.rstrip("/") + "/v1" if "/v1" not in base else base,
        temperature=0.3,
        max_tokens=500,
    )


def _node_llm(state: MinimalState) -> dict:
    llm = _get_llm()
    out = llm.invoke(state["messages"])
    return {"messages": [out]}


def create_minimal_graph() -> StateGraph:
    g = StateGraph(MinimalState)
    g.add_node("llm", _node_llm)
    g.add_edge(START, "llm")
    g.add_edge("llm", END)
    return g


def run_minimal_graph(question: str = "你好，请用一句话介绍你自己。") -> dict:
    """
    运行最小图：用户问题 → LLM → 返回最后一条 AI 消息内容。
    """
    app = create_minimal_graph().compile()
    init = {"messages": [HumanMessage(content=question)]}
    out = app.invoke(init)
    messages = out.get("messages") or []
    last = next((m for m in reversed(messages) if hasattr(m, "content") and m.content), None)
    answer = (getattr(last, "content", None) or "").strip() if last else ""
    return {"answer": answer, "messages": messages}
