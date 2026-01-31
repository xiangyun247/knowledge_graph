#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4.3 / 4.4 Agent 状态、图结构、实现与运行

- State: messages（含 add_messages）
- 节点: agent（LLM+bind_tools）、tools（执行 Tool 调用）
- 边: START→agent；agent 有 tool_calls→tools，否则→END；tools→agent
- 输出: answer（最终 AI 回复）、sources（来自 Tool 的图/文档等）
"""

import os
import logging
from typing import Annotated, Iterator, Literal, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .context import set_agent_user_id
from .tools import get_all_tools

# ToolNode：优先 langgraph.prebuilt，不可用时用手写 tools 节点
try:
    from langgraph.prebuilt import ToolNode
except ImportError:
    ToolNode = None

logger = logging.getLogger(__name__)

# 6.3 系统提示：角色、边界、引用要求
AGENT_SYSTEM_PROMPT = """你是一名医学知识图谱与文献检索助手，负责基于「知识图谱」和「文档知识库」回答用户问题。

规则：
1. 回答必须基于你通过工具检索到的图谱实体、关系与文献片段；明确区分「来自图谱」与「来自文献」的信息。
2. 若检索无结果或工具返回「未找到」「暂时不可用」，应明确告知用户，不要编造内容。
3. 可引用具体实体名、关系或文献出处；涉及诊疗建议时请提示「仅供参考，请遵医嘱」。
4. 对指代、追问（如「它」「这个病」「上面说的」）结合对话上文理解后，选用合适的工具检索再回答。
5. 请使用「正常中文段落」回答，保留合适的换行，不要输出 Markdown 语法（不要使用 * 或 # 开头的标题、列表、加粗符号等）。
6. 不要在答案中描述你的思考或检索过程（例如「让我先搜索一下」「现在我从知识图谱中检索」等），只输出面向医生/患者的最终医学结论和解释；如果需要提到来源，可以用一句「根据知识图谱」或「根据文献检索结果」概括说明即可。"""


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def _get_llm(base_url: str = None, model: str = None, api_key: str = None):
    api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or getattr(
        __import__("config", fromlist=["DEEPSEEK_API_KEY"]), "DEEPSEEK_API_KEY", None
    )
    base = base_url or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    if "/v1" not in base:
        base = base.rstrip("/") + "/v1"
    model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        base_url=base,
        temperature=0.3,
        max_tokens=1500,
    )


def _agent_node(state: AgentState) -> dict:
    llm = _get_llm()
    tools = get_all_tools()
    bound = llm.bind_tools(tools)
    out = bound.invoke(state["messages"])
    return {"messages": [out]}


def _tools_node(state: AgentState) -> dict:
    """手写 tools 节点：当 langgraph.prebuilt.ToolNode 不可用时使用。"""
    last = state["messages"][-1] if state["messages"] else None
    if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
        return {"messages": []}
    name2tool = {t.name: t for t in get_all_tools()}
    out = []
    for tc in last.tool_calls:
        t = name2tool.get(tc.get("name"))
        args = tc.get("args") or {}
        res = str(t.invoke(args)) if t else "[工具不存在]"
        out.append(ToolMessage(content=res, tool_call_id=tc.get("id", "")))
    return {"messages": out}


def create_agent_graph() -> StateGraph:
    tools = get_all_tools()
    if ToolNode is not None:
        tool_node = ToolNode(tools)
    else:
        tool_node = _tools_node

    g = StateGraph(AgentState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", tool_node)

    g.add_edge(START, "agent")

    def route_after_agent(state: AgentState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1] if state["messages"] else None
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "__end__"

    g.add_conditional_edges("agent", route_after_agent)
    g.add_edge("tools", "agent")

    return g


def _collect_sources(messages: Sequence[BaseMessage]) -> list:
    """从 ToolMessage 中收集来源信息，用于右侧「来自图谱 / 文献」面板。"""
    out = []
    for m in messages:
        if isinstance(m, ToolMessage):
            # ToolMessage.name 约定为工具名：graph_retrieve / doc_search 等
            name = getattr(m, "name", None) or ""
            c = getattr(m, "content", None) or ""
            if not c:
                continue
            t = (
                "graph"
                if name in ("graph_retrieve", "graph_list", "graph_data")
                else "entity"
                if name == "entity_search"
                else "doc"
                if name == "doc_search"
                else "tool"
            )
            out.append({"type": t, "content": c[:2000]})
    return out


def _build_trace(
    question: str,
    messages: Sequence[BaseMessage],
    initial_messages: Optional[Sequence[BaseMessage]] = None,
) -> dict:
    """
    构造「深度思考」用的分析 trace：
    - retrievals: 本次回答用到的图谱 / 文献 / 历史会话等来源
    - reasoning: 一个面向用户的自然语言推理步骤摘要
    """
    retrievals = []
    graph_count = 0
    doc_count = 0

    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        name = getattr(m, "name", None) or ""
        c = (getattr(m, "content", None) or "").strip()
        if not c:
            continue
        tool_type = (
            "graph"
            if name in ("graph_retrieve", "graph_list", "graph_data")
            else "entity"
            if name == "entity_search"
            else "doc"
            if name == "doc_search"
            else "tool"
        )
        if tool_type == "graph":
            graph_count += 1
        elif tool_type == "doc":
            doc_count += 1
        snippet = c[:120]
        retrievals.append(
            {
                "type": tool_type,
                "tool": name,
                "snippet": snippet,
            }
        )

    history_used = bool(initial_messages)
    if history_used:
        retrievals.append(
            {
                "type": "history",
                "tool": "session_history",
                "snippet": f"结合了之前 {len(initial_messages)} 轮对话上下文，用于理解指代和追问。",
            }
        )

    reasoning_parts = []
    if graph_count:
        reasoning_parts.append(f"首先通过图谱工具检索到 {graph_count} 条与问题高度相关的实体或关系信息")
    if doc_count:
        reasoning_parts.append(f"随后结合 {doc_count} 条文献片段，对诊疗依据和背景知识进行补充说明")
    if history_used:
        reasoning_parts.append("同时参考本轮会话中的历史提问，保证回答在语义和上下文上前后一致")

    if reasoning_parts:
        prefix = f"围绕你的问题「{question[:30]}」" if question else "围绕你的问题"
        reasoning = prefix + "，" + "，".join(reasoning_parts) + "，最后综合这些信息给出当前回答。"
    else:
        reasoning = (
            "本次回答主要基于模型对问题本身的理解，"
            "没有命中可用的图谱或文献检索结果，因此无法提供更详细的检索链路。"
        )

    return {
        "retrievals": retrievals,
        "reasoning": reasoning,
    }


def _build_initial_messages(question: str, initial_messages: Optional[Sequence[BaseMessage]] = None):
    """[SystemMessage] + initial_messages + [HumanMessage(question)]"""
    msgs: list = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
    if initial_messages:
        msgs.extend(initial_messages)
    msgs.append(HumanMessage(content=question))
    return msgs


def run_agent(
    question: str,
    *,
    initial_messages: Optional[Sequence[BaseMessage]] = None,
    user_id: Optional[str] = None,
    base_url: str = None,
    model: str = None,
    api_key: str = None,
    deep_think: bool = False,
) -> dict:
    """
    运行 Agent：用户问题 → 多步 Tool 调用 → 生成回答。
    - initial_messages: 6.1 对话上文，用于多轮、指代、追问。
    - user_id: 7.1 当前用户，供 doc_search/graph_list/graph_data 做权限过滤。
    返回: { "answer": str, "sources": [...] }
    """
    if user_id is not None:
        set_agent_user_id(user_id)
    app = create_agent_graph().compile()
    init_messages = _build_initial_messages(question, initial_messages)
    init: AgentState = {"messages": init_messages}
    out = app.invoke(init)
    messages = out.get("messages") or []

    answer = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and (getattr(m, "content", None) or "").strip():
            answer = (m.content or "").strip()
            break

    sources = _collect_sources(messages)
    trace = _build_trace(question, messages, initial_messages) if deep_think else None
    return {
        "answer": answer or "抱歉，未能生成回答。",
        "sources": sources,
        "trace": trace,
    }


def run_agent_stream(
    question: str,
    *,
    initial_messages: Optional[Sequence[BaseMessage]] = None,
    user_id: Optional[str] = None,
    deep_think: bool = False,
) -> Iterator[dict]:
    """
    6.2 流式运行 Agent：与 run_agent 逻辑一致，但对 LLM 使用 .stream()。
    7.1 user_id 供 tools 做权限过滤。
    """
    if user_id is not None:
        set_agent_user_id(user_id)
    messages = _build_initial_messages(question, initial_messages)
    llm = _get_llm()
    tools = get_all_tools()
    name2tool = {t.name: t for t in tools}
    full = None

    while True:
        full = None
        for c in llm.bind_tools(tools).stream(messages):
            if full is None:
                full = c
            else:
                full = full + c
            d = getattr(c, "content", None) or ""
            if d:
                yield {"type": "chunk", "delta": d}

        if full is None:
            break
        messages.append(full)
        if not getattr(full, "tool_calls", None):
            break
        yield {"type": "tools"}
        for tc in full.tool_calls:
            name = tc.get("name")
            t = name2tool.get(name)
            args = tc.get("args") or {}
            res = str(t.invoke(args)) if t else "[工具不存在]"
            # 保留 ToolMessage.name，便于前端区分图谱 / 文献 / 实体等来源
            messages.append(
                ToolMessage(
                    content=res,
                    tool_call_id=tc.get("id", ""),
                    name=name or "",
                )
            )

    answer = (full.content or "").strip() if full else ""
    sources = _collect_sources(messages)
    trace = _build_trace(question, messages, initial_messages) if deep_think else None
    yield {
        "type": "done",
        "answer": answer or "抱歉，未能生成回答。",
        "sources": sources,
        "trace": trace,
    }
