"""
基于 MySQL graph_data 的图检索（用户/图谱过滤）

当 user_id 或 graph_id 指定时，从 MySQL knowledge_graphs 的 graph_data 中检索，
实现按用户/图谱过滤的图检索，与 Neo4j 全局检索互补。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _parse_graph_data(g: Dict[str, Any]) -> Tuple[List[Dict], List[Dict]]:
    """解析 graph_data，返回 (nodes, edges)。"""
    d = g.get("graph_data") or {}
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except Exception:
            return [], []
    nodes = d.get("nodes") or []
    edges = d.get("edges") or d.get("relations") or []
    return nodes, edges


def _node_id(n: Dict) -> str:
    """节点唯一标识。"""
    return str(n.get("id") or n.get("name") or id(n))


def _node_name(n: Dict) -> str:
    return str(n.get("name") or n.get("id") or "")


def retrieve_from_mysql_graphs(
    mysql_client: Any,
    entity_names: List[str],
    user_id: Optional[str] = None,
    graph_id: Optional[str] = None,
    max_depth: int = 2,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    从 MySQL 用户图谱中检索（按 user_id/graph_id 过滤）。

    Args:
        mysql_client: MySQL 客户端
        entity_names: 实体名称列表
        user_id: 用户 ID，为 None 时仅查 default 图谱
        graph_id: 指定图谱 ID，为空时查用户全部图谱
        max_depth: 邻居最大跳数
        limit: 返回数量限制

    Returns:
        与 GraphRetriever.retrieve 兼容的格式
    """
    if not entity_names:
        return []

    try:
        if graph_id:
            rec = mysql_client.get_graph_by_id(graph_id)
            if not rec:
                return []
            if user_id and (rec.get("user_id") or "").strip() and rec.get("user_id") != user_id:
                return []
            graphs = [rec]
        else:
            if user_id and user_id != "default_user":
                graphs = mysql_client.get_graphs(user_id=user_id, limit=50)
            else:
                graphs = mysql_client.get_default_graphs(limit=50)

        if not graphs:
            return []

        # 合并所有图谱的节点和边
        id_to_node: Dict[str, Dict] = {}
        name_to_ids: Dict[str, List[str]] = {}
        all_edges: List[Tuple[str, str, str]] = []  # (src_id, tgt_id, label)

        for g in graphs:
            nodes, edges = _parse_graph_data(g)
            for n in nodes:
                nid = _node_id(n)
                name = _node_name(n)
                if nid not in id_to_node:
                    id_to_node[nid] = n
                if name:
                    name_to_ids.setdefault(name, []).append(nid)
            for e in edges:
                src_raw = (e.get("source") or e.get("sourceId") or "").strip()
                tgt_raw = (e.get("target") or e.get("targetId") or "").strip()
                lbl = (e.get("label") or e.get("relation") or "").strip()
                if not src_raw or not tgt_raw:
                    continue
                # 解析 source/target：可能是 id 或 name
                src = src_raw if src_raw in id_to_node else (name_to_ids.get(src_raw, [None])[0] if src_raw in name_to_ids else None)
                tgt = tgt_raw if tgt_raw in id_to_node else (name_to_ids.get(tgt_raw, [None])[0] if tgt_raw in name_to_ids else None)
                if src and tgt and src in id_to_node and tgt in id_to_node:
                    all_edges.append((src, tgt, lbl))

        # 构建邻接表
        adj: Dict[str, List[Tuple[str, str]]] = {nid: [] for nid in id_to_node}
        for src, tgt, lbl in all_edges:
            if src in adj:
                adj[src].append((tgt, lbl))
            if tgt in adj:
                adj[tgt].append((src, lbl))

        entity_set = set(e.strip() for e in entity_names if e.strip())
        name_to_ids: Dict[str, List[str]] = {}
        for nid, n in id_to_node.items():
            name = _node_name(n)
            if name in entity_set:
                name_to_ids.setdefault(name, []).append(nid)

        # 找到匹配的实体 id
        matched_ids: Set[str] = set()
        for name in entity_set:
            matched_ids.update(name_to_ids.get(name, []))

        if not matched_ids:
            return []

        results: List[Dict[str, Any]] = []
        seen_node_ids: Set[str] = set()

        # 1. 直接实体
        for nid in matched_ids:
            if nid in id_to_node and nid not in seen_node_ids:
                n = id_to_node[nid]
                seen_node_ids.add(nid)
                props = n.get("properties", n) if isinstance(n.get("properties"), dict) else dict(n)
                results.append({
                    "type": "entity",
                    "node_id": nid,
                    "labels": [n.get("type") or n.get("label") or "Entity"],
                    "name": _node_name(n),
                    "description": props.get("description", ""),
                    "properties": props,
                    "relevance_score": 1.0,
                    "source": "mysql_graph",
                })

        # 2. 多跳邻居
        depth = min(max_depth, 3)
        frontier = set(matched_ids)
        visited = set(matched_ids)
        hop = 0

        while hop < depth and frontier:
            next_frontier: Set[str] = set()
            for cur in frontier:
                for tgt, lbl in adj.get(cur, []):
                    if tgt not in visited:
                        visited.add(tgt)
                        next_frontier.add(tgt)
                        if tgt in id_to_node and tgt not in seen_node_ids:
                            n = id_to_node[tgt]
                            seen_node_ids.add(tgt)
                            path_names = [id_to_node.get(x, {}).get("name", x) for x in [cur, tgt]]
                            results.append({
                                "type": "neighbor",
                                "node_id": tgt,
                                "labels": [n.get("type") or n.get("label") or "Entity"],
                                "name": _node_name(n),
                                "description": (n.get("properties") or {}).get("description", ""),
                                "properties": n.get("properties", {}),
                                "hop_count": hop + 1,
                                "path_names": path_names,
                                "relation_types": [lbl] if lbl else [],
                                "relevance_score": 1.0 / (1.0 + 0.3 * (hop + 1)),
                                "source": "mysql_graph",
                            })
                            if len(results) >= limit:
                                break
            if len(results) >= limit:
                break
            frontier = next_frontier
            hop += 1

        # 3. 实体间路径（简化：BFS 找最短路径）
        if len(entity_set) >= 2 and len(results) < limit:
            ids_list = list(matched_ids)
            for i in range(min(2, len(ids_list))):
                for j in range(i + 1, min(len(ids_list), i + 3)):
                    start_id, end_id = ids_list[i], ids_list[j]
                    path = _bfs_path(adj, id_to_node, start_id, end_id, max_depth=min(max_depth, 5))
                    if path:
                        path_nodes = [{"name": _node_name(id_to_node.get(pid, {}))} for pid in path]
                        rel_types = []
                        for k in range(len(path) - 1):
                            for tgt, lbl in adj.get(path[k], []):
                                if tgt == path[k + 1]:
                                    rel_types.append(lbl)
                                    break
                        results.append({
                            "type": "path",
                            "start_entity": _node_name(id_to_node.get(start_id, {})),
                            "end_entity": _node_name(id_to_node.get(end_id, {})),
                            "path_length": len(path) - 1,
                            "path_nodes": path_nodes,
                            "relation_types": rel_types,
                            "relevance_score": 1.0 / (1.0 + 0.2 * (len(path) - 1)),
                            "source": "mysql_graph",
                        })
                        if len(results) >= limit:
                            break

        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results[:limit]

    except Exception as e:
        logger.error("MySQL 图检索失败: %s", e)
        return []


def _bfs_path(
    adj: Dict[str, List[Tuple[str, str]]],
    id_to_node: Dict[str, Dict],
    start: str,
    end: str,
    max_depth: int = 5,
) -> Optional[List[str]]:
    """BFS 找最短路径。"""
    if start not in id_to_node or end not in id_to_node:
        return None
    from collections import deque
    q = deque([(start, [start])])
    seen = {start}
    while q:
        cur, path = q.popleft()
        if len(path) > max_depth:
            continue
        if cur == end:
            return path
        for tgt, _ in adj.get(cur, []):
            if tgt not in seen:
                seen.add(tgt)
                q.append((tgt, path + [tgt]))
    return None
