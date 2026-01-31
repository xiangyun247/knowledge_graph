#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4.2 将现有能力封装为 LangChain Tool

- graph_retrieve: 图检索 GraphRetriever.retrieve
- entity_search: 实体搜索 Neo4j.search_entities（或 MySQL 回退）
- doc_search: 文档检索 ChromaStore.search
- graph_list: 图谱列表 mysql.get_graphs
- graph_data: 图谱数据（节点、边）mysql + graph_data 解析
"""

import json
import logging
from typing import Optional, List

from langchain_core.tools import tool

from .context import get_agent_user_id

logger = logging.getLogger(__name__)

# 懒加载单例，避免循环导入与启动时必连
_neo4j = None
_mysql = None
_chroma = None
_graph_retriever = None


def _neo4j_client():
    global _neo4j
    if _neo4j is not None:
        return _neo4j
    try:
        from db.neo4j_client import Neo4jClient
        c = Neo4jClient()
        if c.verify_connection():
            _neo4j = c
            return _neo4j
    except Exception as e:
        logger.warning("Neo4j 不可用: %s", e)
    return None


def _mysql_client():
    global _mysql
    if _mysql is not None:
        return _mysql
    try:
        from db.mysql_client import get_mysql_client
        _mysql = get_mysql_client()
        return _mysql
    except Exception as e:
        logger.warning("MySQL 不可用: %s", e)
    return None


def _chroma_store():
    global _chroma
    if _chroma is not None:
        return _chroma
    try:
        from backend.chroma_store import ChromaStore
        _chroma = ChromaStore()
        return _chroma
    except Exception as e:
        logger.warning("ChromaStore 不可用: %s", e)
    return None


def _graph_retriever_impl():
    global _graph_retriever
    if _graph_retriever is not None:
        return _graph_retriever
    nc = _neo4j_client()
    if nc is None:
        return None
    try:
        from rag.graph_retriever import GraphRetriever
        _graph_retriever = GraphRetriever(nc)
        return _graph_retriever
    except Exception as e:
        logger.warning("GraphRetriever 不可用: %s", e)
    return None


# ---------- entity_search 的 MySQL 回退（与 app._search_graph_entities 逻辑一致）----------
def _entity_search_mysql(keyword: str, node_type: str, limit: int) -> List[dict]:
    mc = _mysql_client()
    if not mc:
        return []
    uid = get_agent_user_id()
    try:
        graphs = mc.get_graphs(user_id=uid, limit=50)
        out = []
        seen = set()
        for g in graphs:
            d = g.get("graph_data") or {}
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except Exception:
                    d = {}
            nodes = d.get("nodes") or []
            for n in nodes:
                nid = n.get("id") or n.get("name")
                if not nid or nid in seen:
                    continue
                try:
                    txt = json.dumps(n, ensure_ascii=False)
                except Exception:
                    txt = str(n)
                match_k = (not keyword) or (keyword.lower() in txt.lower())
                match_t = (not node_type) or (node_type == n.get("type"))
                if match_k and match_t:
                    seen.add(nid)
                    out.append({
                        "id": nid,
                        "name": n.get("name") or nid,
                        "type": n.get("type") or n.get("label") or "entity",
                        "properties": n.get("properties", {}),
                    })
        return out[:limit]
    except Exception as e:
        logger.warning("MySQL 实体搜索失败: %s", e)
        return []


# ---------- Tools ----------

@tool
def graph_retrieve(
    query: str,
    entity_names: str = "",
    max_depth: int = 2,
    limit: int = 10,
) -> str:
    """
    从医学知识图谱中检索与给定实体相关的多跳邻居、关系路径、子图。适合回答：某病的症状/并发症/用药/检查、实体间关系、病因链等。
    请优先使用本工具获取「来自图谱」的医学实体与关系，再结合 doc_search 的文献做回答。
    参数：query 为用户问题或检索意图；entity_names 为已知实体名，多个用逗号分隔（如「胰腺炎,腹痛」），空时尝试从 query 推断；max_depth 建议 1~2，过深易噪声；limit 默认 10。
    """
    gr = _graph_retriever_impl()
    if gr is None:
        return "[图检索暂时不可用：Neo4j 未连接或 GraphRetriever 初始化失败]"
    names = [x.strip() for x in (entity_names or "").split(",") if x.strip()]
    if not names:
        nc = _neo4j_client()
        if nc:
            try:
                ents = nc.search_entities(query, limit=5)
                names = [e.get("name") or "" for e in ents if e.get("name")]
            except Exception:
                pass
    if not names:
        return "[图检索需要至少一个实体名称；entity_names 为空且无法从 query 推断]"
    try:
        res = gr.retrieve(query=query, entity_names=names, max_depth=max_depth, limit=limit)
        return gr.format_results_for_context(res, max_length=3000)
    except Exception as e:
        return f"[图检索异常: {e}]"


@tool
def entity_search(
    keyword: str,
    node_type: str = "",
    limit: int = 10,
) -> str:
    """
    按关键词在知识图谱中查找实体（疾病、症状、药物、治疗、检查等）。用于：确认实体是否存在、获取实体类型与简述、为 graph_retrieve 提供 entity_names。与 graph_retrieve 配合：先 entity_search 定实体，再 graph_retrieve 查关系。
    参数：keyword 必填，如「胰腺炎」「二甲双胍」；node_type 可选，如 Disease/Symptom/Medicine/Treatment/Examination，空为全部；limit 默认 10。
    """
    nc = _neo4j_client()
    if nc:
        try:
            ents = nc.search_entities(keyword, node_type=node_type or None, limit=limit)
            if ents:
                lines = []
                for e in ents:
                    n = e.get("name") or e.get("id") or ""
                    t = e.get("type") or ""
                    d = (e.get("properties") or {}).get("description", "")
                    lines.append(f"- {n} ({t})" + (f": {d[:80]}…" if d else ""))
                return "\n".join(lines) if lines else "[未找到匹配实体]"
        except Exception as e:
            logger.warning("Neo4j entity_search 失败: %s", e)
    out = _entity_search_mysql(keyword, node_type or "", limit)
    if not out:
        return "[实体搜索暂时不可用或未找到匹配实体]"
    lines = [f"- {e.get('name','')} ({e.get('type','')})" for e in out]
    return "\n".join(lines)


@tool
def doc_search(
    query: str,
    k: int = 5,
    source_type: str = "",
) -> str:
    """
    在文档知识库（已入库的 PDF/TXT/JSON）中做语义检索，返回与问题相关的文献片段。7.1 仅检索当前用户知识库。用于：需要指南、教材、文献出处的回答；与 graph_retrieve/entity_search 互补。库为空或未命中时返回提示，切勿捏造。
    参数：query 为自然语言问题或关键词；k 默认 5，最大 20；source_type 可选 pdf/txt/json 过滤，空为全部。
    """
    cs = _chroma_store()
    if cs is None:
        return "[文档检索暂时不可用：Chroma/Embedding 未就绪]"
    try:
        uid = get_agent_user_id()
        if uid and source_type:
            where = {"$and": [{"user_id": uid}, {"source_type": source_type}]}
        elif uid:
            where = {"user_id": uid}
        elif source_type:
            where = {"source_type": source_type}
        else:
            where = None
        hits = cs.search(query_text=query.strip(), k=min(k, 20), where=where)
        if not hits:
            return "[文档库中未找到相关文献]"
        lines = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata") or {}
            src = meta.get("source_file", "未知")
            st = meta.get("source_type", "")
            text = (h.get("text") or "")[:400]
            lines.append(f"[{i}] {src} ({st}): {text}…")
        return "\n\n".join(lines)
    except Exception as e:
        return f"[文档检索异常: {e}]"


@tool
def graph_list() -> str:
    """获取当前用户可用的知识图谱列表（7.1 按 user_id 过滤），含 id、名称、节点数、关系数。在用户问「有哪些图谱」「图谱列表」或需要先选 graph_id 再查 graph_data 时使用。返回的 graph_id 可作为 graph_data 的入参。"""
    mc = _mysql_client()
    if not mc:
        return "[图谱列表暂时不可用：MySQL 未连接]"
    try:
        uid = get_agent_user_id()
        rows = mc.get_graphs(user_id=uid, limit=50)
        if not rows:
            return "[当前没有知识图谱]"
        lines = []
        for r in rows:
            gid = r.get("graph_id") or r.get("id", "")
            name = r.get("graph_name") or r.get("name", "")
            ne = r.get("entity_count") or 0
            nr = r.get("relation_count") or 0
            lines.append(f"- {gid}\t{name}\t节点{ne} 关系{nr}")
        return "\n".join(lines)
    except Exception as e:
        return f"[图谱列表异常: {e}]"


@tool
def graph_data(
    graph_id: str = "",
    limit: int = 100,
) -> str:
    """
    获取指定知识图谱的节点与边（关系）的文本摘要；7.1 仅可访问当前用户的图谱。graph_id 来自 graph_list；空则合并当前用户所有图谱。limit 控制节点数上限，默认 100。与 graph_retrieve 区别：本工具返回原始结构摘要，graph_retrieve 做基于实体的相关子图检索。
    """
    mc = _mysql_client()
    if not mc:
        return "[图谱数据暂时不可用：MySQL 未连接]"
    try:
        uid = get_agent_user_id()
        if graph_id:
            rec = mc.get_graph_by_id(graph_id)
            if rec and uid and (rec.get("user_id") or "").strip() and rec.get("user_id") != uid:
                return "[无权访问该图谱]"
            graphs = [rec] if rec else []
        else:
            graphs = mc.get_graphs(user_id=uid, limit=20)
        all_nodes = []
        all_edges = []
        seen_n = set()
        for g in graphs:
            d = g.get("graph_data") or {}
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except Exception:
                    d = {}
            nodes = d.get("nodes") or []
            edges = d.get("relations") or d.get("edges") or []
            for n in nodes:
                nid = n.get("id") or n.get("name")
                if nid and nid not in seen_n and len(all_nodes) < limit:
                    seen_n.add(nid)
                    all_nodes.append(n)
            for e in edges:
                s = e.get("source") or e.get("sourceId")
                t = e.get("target") or e.get("targetId")
                l = e.get("label") or e.get("relation") or ""
                if s and t:
                    all_edges.append(f"  {s} --[{l}]--> {t}")
        if not all_nodes and not all_edges:
            return "[没有可用的图谱数据]"
        lines = ["节点:", *[f"  - {n.get('name') or n.get('id')} ({n.get('type') or n.get('label')})" for n in all_nodes[:50]], "关系:", *all_edges[:80]]
        return "\n".join(lines)
    except Exception as e:
        return f"[图谱数据异常: {e}]"


# ---------- 7.2 更多 Tool ----------

@tool
def get_kg_build_status(task_id: str) -> str:
    """
    查询知识图谱构建任务是否跑完、进度与结果。用于「帮我查一下某任务有没有跑完」「任务 xxx 进度」等。
    支持 /api/kg/build 单文件任务与 /api/hadoop/build/batch 批量任务的 task_id。
    参数：task_id 必填，从创建任务时返回的 task_id 获取。
    """
    try:
        from backend.task_status import get_kg_build_status_impl
        r = get_kg_build_status_impl(task_id)
    except Exception as e:
        return f"[查询任务状态异常: {e}]"
    if not r.get("found"):
        return f"任务 {task_id} 不存在。"
    s = r.get("status", "")
    p = r.get("progress", 0)
    msg = r.get("message", "")
    line = f"状态: {s}，进度: {p}%，{msg}"
    if s == "completed":
        line += f"；实体 {r.get('entities_created', 0)}，关系 {r.get('relations_created', 0)}。"
    elif s == "failed":
        line += "（构建失败）。"
    return line


@tool
def list_my_graphs() -> str:
    """列举当前用户的知识图谱（我的图谱）。用于「我有哪些图谱」「我的知识库」等。返回 graph_id、名称、节点数、关系数；graph_id 可用于 get_graph_snapshot 或 graph_data。"""
    return graph_list.invoke({})


@tool
def get_graph_snapshot(graph_id: str, limit: int = 50) -> str:
    """
    获取指定知识图谱的简要快照（节点与关系摘要）。用于「某图谱有啥」「图谱 xxx 的结构」等。graph_id 来自 list_my_graphs 或 graph_list。limit 默认 50，控制节点/关系展示数量。
    """
    mc = _mysql_client()
    if not mc:
        return "[图谱快照暂时不可用：MySQL 未连接]"
    try:
        uid = get_agent_user_id()
        rec = mc.get_graph_by_id(graph_id)
        if not rec:
            return f"图谱 {graph_id} 不存在。"
        if uid and (rec.get("user_id") or "").strip() and rec.get("user_id") != uid:
            return "[无权访问该图谱]"
        d = rec.get("graph_data") or {}
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                d = {}
        nodes = d.get("nodes") or []
        edges = d.get("relations") or d.get("edges") or []
        nn = len(nodes)
        ne = len(edges)
        name = rec.get("graph_name") or rec.get("name") or graph_id
        head = f"图谱 {name}（{graph_id}）：共 {nn} 节点、{ne} 关系。"
        node_sample = [f"{n.get('name') or n.get('id')} ({n.get('type') or n.get('label')})" for n in nodes[:limit]]
        edge_sample = [f"{e.get('source')} --[{e.get('label') or e.get('relation')}]--> {e.get('target')}" for e in edges[:limit]]
        parts = [head]
        if node_sample:
            parts.append("节点示例: " + "; ".join(node_sample[:15]))
        if edge_sample:
            parts.append("关系示例: " + "; ".join(edge_sample[:15]))
        return "\n".join(parts)
    except Exception as e:
        return f"[图谱快照异常: {e}]"


def get_all_tools():
    return [
        graph_retrieve,
        entity_search,
        doc_search,
        graph_list,
        graph_data,
        get_kg_build_status,
        list_my_graphs,
        get_graph_snapshot,
    ]
