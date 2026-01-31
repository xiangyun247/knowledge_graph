#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4.1 最小 LangGraph 图单测

- 验证 create_minimal_graph 可构建
- 有 DEEPSEEK_API_KEY 时跑 run_minimal_graph（否则 skip）
"""

import os
import pytest

# 跳过整个模块：langgraph / langchain 未安装
try:
    from langgraph.graph import StateGraph, START, END
    from langchain_core.messages import HumanMessage
except ImportError:
    pytest.skip("langgraph/langchain 未安装", allow_module_level=True)

# 从 backend.agent 导入需在 skip 之后，否则 skip 前会报错
import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def test_create_minimal_graph():
    """最小图可构建：START -> llm -> END"""
    from backend.agent.minimal_graph import create_minimal_graph

    g = create_minimal_graph()
    assert g is not None
    compiled = g.compile()
    assert compiled is not None


@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="需要 DEEPSEEK_API_KEY 才能调用 LLM"
)
def test_run_minimal_graph():
    """有 API Key 时运行最小图，返回 answer 与 messages"""
    from backend.agent.minimal_graph import run_minimal_graph

    out = run_minimal_graph("你好，请用一句话介绍你自己。")
    assert "answer" in out
    assert "messages" in out
    assert isinstance(out["answer"], str)
    assert len(out["answer"]) > 0
