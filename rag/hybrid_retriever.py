"""
Hybrid RAG：统一结果格式与 RRF 融合

- HybridItem：图/文档/关键词三路检索的统一单条结果格式
- rrf_fuse：多路排序列表的 RRF（Reciprocal Rank Fusion）融合
"""

from typing import Any, Dict, List

import logging

logger = logging.getLogger(__name__)


def _get_default_rrf_k() -> int:
    """从 config 读取 RRF k，未配置时默认 60。"""
    try:
        import config
        return getattr(config, "HYBRID_RAG_RRF_K", 60)
    except Exception:
        return 60


# RRF 常数，优先从 config.HYBRID_RAG_RRF_K 读取
DEFAULT_RRF_K = _get_default_rrf_k()

# 统一单条结果格式的字段名
SOURCE_GRAPH = "graph"
SOURCE_DOC = "doc"
SOURCE_KEYWORD = "keyword"


def make_hybrid_item(
    content: str,
    source: str,
    rank: int,
    content_key: str,
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构造一条 HybridItem。

    Args:
        content: 用于拼上下文的文本
        source: "graph" | "doc" | "keyword"
        rank: 在该路检索中的排名，1-based
        content_key: 用于去重的键
        raw: 原始结果，便于来源展示与调试

    Returns:
        符合 HybridItem 结构的字典
    """
    return {
        "content": content,
        "source": source,
        "rank": rank,
        "content_key": content_key,
        "raw": raw,
    }


def rrf_fuse(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = DEFAULT_RRF_K,
) -> List[Dict[str, Any]]:
    """
    多路排序结果的 RRF（Reciprocal Rank Fusion）融合。

    对每条结果按 content_key 去重，同一 key 只保留一条（首次出现），
    其 RRF 分数为各路中该 key 的 1/(k+rank) 之和；最终按 rrf_score 降序返回。

    Args:
        ranked_lists: 多路结果列表，每路已按相关度排好序，每项为 HybridItem 结构（至少含 content_key）
        k: RRF 常数，通常 60

    Returns:
        按 RRF 分数降序排列的 HybridItem 列表，每项增加 "rrf_score" 字段
    """
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}

    for one_list in ranked_lists:
        for rank, item in enumerate(one_list, start=1):
            key = item.get("content_key")
            if not key:
                key = f"_no_key_{id(item)}"
                logger.warning("HybridItem 缺少 content_key，使用 fallback")
            rrf_contrib = 1.0 / (k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_contrib
            if key not in items:
                # 浅拷贝，避免修改原始 item
                items[key] = {**item}
            items[key]["rrf_score"] = scores[key]

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    result = [items[ck] for ck in sorted_keys]
    logger.debug("rrf_fuse: %d 路 -> %d 条", len(ranked_lists), len(result))
    return result


def fuse_hybrid_three_way(
    graph_items: List[Dict[str, Any]],
    doc_items: List[Dict[str, Any]],
    keyword_items: List[Dict[str, Any]],
    k: int = DEFAULT_RRF_K,
) -> List[Dict[str, Any]]:
    """
    三路 HybridItem 结果做 RRF 融合 + 按 content_key 去重。

    输入三列 [HybridItem]（图 / 文档 / 关键词），输出按 RRF 分数降序排列的 HybridItem 列表。
    同 content_key 只保留一条（取各路贡献之和作为 rrf_score）。

    Args:
        graph_items: 图检索转换后的 HybridItem 列表
        doc_items: Chroma 文档检索转换后的 HybridItem 列表
        keyword_items: 关键词检索转换后的 HybridItem 列表
        k: RRF 常数，通常 60

    Returns:
        排序后的 HybridItem 列表，每项含 "rrf_score" 字段
    """
    return rrf_fuse([graph_items, doc_items, keyword_items], k=k)


def _graph_result_to_text(r: Dict[str, Any]) -> str:
    """
    将图检索单条结果转为用于上下文的文本。
    兼容 GraphRetriever 返回的 entity / neighbor / path / related_entity 等类型。
    """
    name = r.get("name") or ""
    desc = r.get("description") or ""
    parts = []

    if name:
        parts.append(name)
    if desc:
        parts.append(desc)

    rtype = r.get("type", "")
    if rtype == "path":
        start_ = r.get("start_entity", "")
        end_ = r.get("end_entity", "")
        path_nodes = r.get("path_nodes", [])
        rel_types = r.get("relation_types", [])
        if start_ and end_:
            parts.append(f"路径: {start_} -> {end_}")
        if path_nodes:
            names_on_path = [
                (n.get("name", "") or str(n)) if isinstance(n, dict) else str(n)
                for n in path_nodes
            ]
            parts.append("路径节点: " + " -> ".join(filter(None, names_on_path)))
        if rel_types:
            parts.append("关系: " + ", ".join(rel_types))
    elif rtype == "neighbor":
        hop = r.get("hop_count")
        path_names = r.get("path_names", [])
        rel_types = r.get("relation_types", [])
        if hop is not None:
            parts.append(f"({hop}跳邻居)")
        if path_names:
            parts.append("路径: " + " -> ".join(str(x) for x in path_names))
        if rel_types:
            parts.append("关系: " + ", ".join(rel_types))
    else:
        rel_type = r.get("relation_type")
        if rel_type:
            parts.append(f"关系: {rel_type}")

    if not parts:
        # 兜底：用 properties 或 raw 的字符串表示
        props = r.get("properties", r)
        if isinstance(props, dict):
            parts.append(str(props)[:500])
        else:
            parts.append(str(r)[:500])
    return " | ".join(p for p in parts if p)


def graph_results_to_hybrid(
    graph_results: List[Dict[str, Any]],
    top_k_per_source: int = 15,
) -> List[Dict[str, Any]]:
    """
    将 GraphRetriever.retrieve 返回的图检索结果转为 HybridItem 列表。

    Args:
        graph_results: 图检索原始结果（含 type, node_id/start_entity 等）
        top_k_per_source: 最多取前几条参与融合

    Returns:
        HybridItem 列表，source=SOURCE_GRAPH
    """
    items = []
    for rank, r in enumerate(graph_results[:top_k_per_source], start=1):
        content = _graph_result_to_text(r)
        # content_key：有 node_id 用 node_id，path 用 start_end，否则用 rank 区分
        node_id = r.get("node_id")
        if node_id is not None:
            content_key = f"graph:{node_id}"
        elif r.get("type") == "path":
            s = r.get("start_entity", "")
            e = r.get("end_entity", "")
            content_key = f"graph:path:{s}_{e}"
        else:
            content_key = f"graph:rank_{rank}_{id(r)}"
        items.append(
            make_hybrid_item(
                content=content,
                source=SOURCE_GRAPH,
                rank=rank,
                content_key=content_key,
                raw=r,
            )
        )
    return items


def chroma_results_to_hybrid(
    chroma_results: List[Dict[str, Any]],
    top_k_per_source: int = 15,
) -> List[Dict[str, Any]]:
    """
    将 ChromaStore.search 返回的文档检索结果转为 HybridItem 列表。

    ChromaStore.search 返回格式：[{"id", "text", "metadata", "distance"}, ...]
    调用方需在 search 时传入 where 参数（如 {"user_id": user_id}）做过滤。

    Args:
        chroma_results: ChromaStore.search 的返回值
        top_k_per_source: 最多取前几条参与融合

    Returns:
        HybridItem 列表，source=SOURCE_DOC
    """
    items = []
    for rank, r in enumerate(chroma_results[:top_k_per_source], start=1):
        content = r.get("text", "")
        chunk_id = r.get("id", "")
        content_key = f"doc:{chunk_id}" if chunk_id else f"doc:rank_{rank}_{id(r)}"
        items.append(
            make_hybrid_item(
                content=content,
                source=SOURCE_DOC,
                rank=rank,
                content_key=content_key,
                raw=r,
            )
        )
    return items


def keyword_results_to_hybrid(
    keyword_results: List[Dict[str, Any]],
    top_k_per_source: int = 15,
) -> List[Dict[str, Any]]:
    """
    将 RAGPipeline._keyword_search 返回的关键词检索结果转为 HybridItem 列表。

    _keyword_search 返回格式：[{"type","node_id","name","description","properties",...}, ...]

    Args:
        keyword_results: 关键词检索原始结果（含 node_id, name, description 等）
        top_k_per_source: 最多取前几条参与融合

    Returns:
        HybridItem 列表，source=SOURCE_KEYWORD
    """
    items = []
    for rank, r in enumerate(keyword_results[:top_k_per_source], start=1):
        content = r.get("description") or r.get("name", "")
        node_id = r.get("node_id")
        content_key = f"keyword:{node_id}" if node_id is not None else f"keyword:rank_{rank}_{id(r)}"
        items.append(
            make_hybrid_item(
                content=content,
                source=SOURCE_KEYWORD,
                rank=rank,
                content_key=content_key,
                raw=r,
            )
        )
    return items
