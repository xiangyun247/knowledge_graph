#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4.3 / 4.4 LangGraph Agent 单测

- create_agent_graph 可构建、可 compile
- get_all_tools 返回 5 个 Tool
- 有 DEEPSEEK_API_KEY 时跑 run_agent，检查 answer、sources
"""

import os
import pytest

try:
    from langgraph.graph import StateGraph, START, END
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
except ImportError:
    pytest.skip("langgraph/langchain 未安装", allow_module_level=True)

import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def test_get_all_tools():
    """get_all_tools 返回 5 个工具"""
    from backend.agent.tools import get_all_tools

    tools = get_all_tools()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert "graph_retrieve" in names
    assert "entity_search" in names
    assert "doc_search" in names
    assert "graph_list" in names
    assert "graph_data" in names


def test_create_agent_graph():
    """Agent 图可构建、可 compile"""
    from backend.agent.agent import create_agent_graph

    g = create_agent_graph()
    assert g is not None
    app = g.compile()
    assert app is not None


def test_collect_sources():
    """_collect_sources 能从 ToolMessage 提取 type 与 content"""
    from backend.agent.agent import _collect_sources

    messages = [
        ToolMessage(content="图检索结果…", name="graph_retrieve", tool_call_id="a"),
        ToolMessage(content="文档片段…", name="doc_search", tool_call_id="b"),
    ]
    sources = _collect_sources(messages)
    assert len(sources) == 2
    typs = [s["type"] for s in sources]
    assert "graph" in typs
    assert "doc" in typs


@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="需要 DEEPSEEK_API_KEY 才能调用 LLM"
)
def test_run_agent():
    """有 API Key 时运行 Agent，返回 answer 与 sources"""
    from backend.agent.agent import run_agent

    out = run_agent("胰腺炎有哪些症状？")
    assert "answer" in out
    assert "sources" in out
    assert isinstance(out["answer"], str)
    assert isinstance(out["sources"], list)
    # answer 非空（可能直接回答，也可能基于 tool 结果）
    assert len(out["answer"]) > 0
