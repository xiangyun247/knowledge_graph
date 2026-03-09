# Hybrid RAG 改造步骤与接口设计

本文档给出「图检索 + Chroma 文档向量 + 关键词」三路检索、RRF 融合的改造步骤与接口/伪代码，便于在现有 RAG 与 Agent 上落地。

---

## 一、目标与约定

- **三路检索**：图检索（Neo4j）、文档向量检索（Chroma）、关键词检索（Neo4j/Cypher 或现有实现）。
- **统一格式**：每条结果转为统一结构，便于去重与 RRF。
- **融合方式**：RRF（Reciprocal Rank Fusion），k 默认 60。
- **兼容现有**：不破坏现有 `RAGPipeline.answer()` 与 Agent tools，通过新增「混合检索」入口接入。

---

## 二、统一结果格式

所有来源的结果都先归一为同一结构，便于 RRF 和后续上下文构建。

```python
# 统一单条结果格式（伪代码）
HybridItem = {
    "content": str,        # 用于拼上下文的文本（必填）
    "source": str,         # "graph" | "doc" | "keyword"
    "rank": int,           # 在该路检索中的排名，1-based
    "raw": dict,           # 原始结果，便于来源展示与调试
    "content_key": str,    # 用于去重的键，如 node_id、chunk_id、text 哈希
}
```

- **content**：图检索可为「实体名 + 关系 + 描述」拼接；文档为 chunk 文本；关键词为命中片段。
- **content_key**：同一条逻辑结果只保留一条（多路都命中时按 RRF 合并），如 `graph:node_123`、`doc:chunk_456`、`keyword:hash_xxx`。

---

## 三、改造步骤概览

| 步骤 | 内容 | 涉及文件/模块 |
|------|------|----------------|
| 1 | 定义统一结果格式与 RRF 函数 | 新建 `rag/hybrid_retriever.py` 或放在 `rag_pipeline.py` |
| 2 | 图检索结果 → 转成 HybridItem 列表 | 复用 `GraphRetriever.retrieve`，后处理 |
| 3 | Chroma 文档检索 → 转成 HybridItem 列表 | 调用 `ChromaStore.search`，按 user_id 等过滤 |
| 4 | 关键词检索 → 转成 HybridItem 列表 | 复用现有 `_keyword_search`，后处理 |
| 5 | 三路结果做 RRF 融合 + 按 content_key 去重 | 单函数：输入三列 [HybridItem]，输出排序后的 HybridItem 列表 |
| 6 | 在 RAG 管线中接入混合检索 | `rag_pipeline.py` 中新增 `_retrieve_hybrid()`，或替换 `_retrieve_information` 的融合逻辑 |
| 7 | （可选）Agent 增加 hybrid_retrieve tool | `backend/agent/tools.py` 增加一个 tool，内部调步骤 6 |

---

## 四、接口与伪代码

### 4.1 RRF 融合

```python
# 伪代码：RRF
def rrf_fuse(ranked_lists: List[List[HybridItem]], k: int = 60) -> List[HybridItem]:
    """
    ranked_lists: [图检索结果列表, 文档检索结果列表, 关键词检索结果列表]，每个列表已按相关度排好序
    k: RRF 常数，通常 60
    返回: 按 RRF 分数排序后的合并列表，同 content_key 只保留一条（取最大 RRF 分）
    """
    scores = {}  # content_key -> rrf_score
    items = {}   # content_key -> HybridItem（保留 content、source、raw 等）

    for rank, item in enumerate(each_item_in_each_list, start=1):  # 1-based rank
        key = item["content_key"]
        rrf_contrib = 1.0 / (k + rank)
        scores[key] = scores.get(key, 0.0) + rrf_contrib
        if key not in items or rank < items[key].get("rank", 999):
            items[key] = {**item, "rrf_score": scores[key]}

    # 按 RRF 分降序
    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [items[k] for k in sorted_keys]
```

### 4.2 图检索 → HybridItem

```python
# 伪代码：图检索结果归一化
def graph_results_to_hybrid(graph_results: List[Dict], top_k_per_source: int) -> List[HybridItem]:
    items = []
    for rank, r in enumerate(graph_results[:top_k_per_source], start=1):
        content = _graph_result_to_text(r)  # 把 entity/relation/description 拼成一段文本
        key = f"graph:{r.get('node_id', id(r))}"
        items.append({
            "content": content,
            "source": "graph",
            "rank": rank,
            "raw": r,
            "content_key": key,
        })
    return items
```

### 4.3 Chroma 文档检索 → HybridItem

```python
# 伪代码：Chroma 结果归一化
def chroma_results_to_hybrid(
    chroma_results: List[Dict],  # ChromaStore.search 返回的 [{"id","text","metadata","distance"}]
    top_k_per_source: int,
) -> List[HybridItem]:
    items = []
    for rank, r in enumerate(chroma_results[:top_k_per_source], start=1):
        items.append({
            "content": r.get("text", ""),
            "source": "doc",
            "rank": rank,
            "raw": r,
            "content_key": f"doc:{r.get('id', rank)}",
        })
    return items
```

### 4.4 关键词检索 → HybridItem

```python
# 伪代码：关键词结果归一化（与现有 _keyword_search 返回格式对齐）
def keyword_results_to_hybrid(keyword_results: List[Dict], top_k_per_source: int) -> List[HybridItem]:
    items = []
    for rank, r in enumerate(keyword_results[:top_k_per_source], start=1):
        content = r.get("description") or r.get("name", "")
        key = f"keyword:{r.get('node_id', id(r))}"
        items.append({
            "content": content,
            "source": "keyword",
            "rank": rank,
            "raw": r,
            "content_key": key,
        })
    return items
```

### 4.5 混合检索主入口（供 RAG 或 Agent 调用）

```python
# 伪代码：混合检索主入口
def hybrid_retrieve(
    query: str,
    parsed_query: Dict,           # 含 entities, normalized_query, keywords
    *,
    top_k: int = 10,             # 最终返回条数
    top_k_per_source: int = 15,   # 每路最多取几条再参与 RRF
    use_graph: bool = True,
    use_doc_vector: bool = True,  # Chroma
    use_keyword: bool = True,
    user_id: Optional[str] = None,  # Chroma 按用户过滤
) -> List[HybridItem]:
    graph_items, doc_items, keyword_items = [], [], []

    entity_names = [e["name"] for e in parsed_query.get("entities", [])]
    query_text = parsed_query.get("normalized_query", query)

    if use_graph and entity_names:
        graph_results = graph_retriever.retrieve(query_text, entity_names, limit=top_k_per_source)
        graph_items = graph_results_to_hybrid(graph_results, top_k_per_source)

    if use_doc_vector and chroma_store:
        where = {"user_id": user_id} if user_id else None
        doc_results = chroma_store.search(query_text, k=top_k_per_source, where=where)
        doc_items = chroma_results_to_hybrid(doc_results, top_k_per_source)

    if use_keyword:
        keywords = parsed_query.get("keywords", []) or [query_text]
        kw_results = _keyword_search(keywords, limit=top_k_per_source)
        keyword_items = keyword_results_to_hybrid(kw_results, top_k_per_source)

    fused = rrf_fuse([graph_items, doc_items, keyword_items], k=60)
    return fused[:top_k]
```

---

## 五、与现有 RAG 管线对接

- **方式 A（推荐）**：在 `rag_pipeline.py` 中新增 `_retrieve_hybrid()`，返回 `List[HybridItem]`；在 `answer()` 里若启用 hybrid，则调用 `_retrieve_hybrid()`，再把 `[item["content"] for item in fused]` 交给 `_build_context()`。
- **方式 B**：保留现有 `_retrieve_information()` 的图 + 向量 + 关键词逻辑，仅把「向量」一路改为同时包含：  
  - 现有 Neo4j 节点向量检索（可选保留），  
  - **Chroma 文档检索**（新增），  
  两路都转成统一格式后一起参与 `_deduplicate_and_rank` 或改为 RRF。

建议先实现 **方式 A**：单独实现 `_retrieve_hybrid()` 与 RRF，再在 `answer()` 中加开关（如 `use_hybrid=True`），便于对比效果。

---

## 六、与 Agent 对接（可选）

- 在 `backend/agent/tools.py` 中新增 tool，例如：

```python
@tool
def hybrid_retrieve(query: str, top_k: int = 10) -> str:
    """混合检索：图+文档+关键词，RRF 融合。返回拼接后的上下文文本。"""
    # 1. 解析 query（可复用 query_parser 或简化为仅实体/关键词）
    # 2. 调用 hybrid_retrieve(..., user_id=get_agent_user_id())
    # 3. 将返回的 HybridItem 的 content 用换行拼成一段字符串
    # 4. return 该字符串
```

- Agent 在需要「综合多源知识」时调用该 tool，而不是分别调 graph_retrieve 与 doc_search，以体现 Hybrid RAG 能力。

---

## 七、配置与依赖

- **Chroma**：已有 `ChromaStore` 与 `EmbeddingClient`，无需新依赖。
- **user_id**：文档检索建议带 `user_id`（与现有 KB 隔离一致）；图检索若按用户过滤图谱，需在 `graph_retriever` 或上层传入当前用户。
- **RRF k**：已支持配置项 `config.HYBRID_RAG_RRF_K`，环境变量 `HYBRID_RAG_RRF_K`，默认 60。
- **API**：`POST /api/query` 支持请求体 `use_hybrid: true` 启用 Hybrid RAG；`user_id` 从 Authorization/X-User-Id 自动获取。

---

## 八、实现顺序建议

1. 在 `rag/` 下实现 `rrf_fuse` 与三种 `*_to_hybrid`，以及 `hybrid_retrieve()`（可放在 `rag_pipeline.py` 或新建 `rag/hybrid_retriever.py`）。
2. 在 `RAGPipeline` 中增加 `_retrieve_hybrid()`，并在 `answer()` 中增加 `use_hybrid` 分支，验证端到端效果。
3. 若效果满意，再将「向量」一路默认改为包含 Chroma，或全面切到 RRF。
4. 最后（可选）在 Agent 中增加 `hybrid_retrieve` tool，并更新文档/README 中的「Hybrid RAG」说明。

按上述步骤即可在现有工程上以较小改动完成 Hybrid RAG 改造，并保留与现有 RAG、Agent 的兼容性。
