#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chroma 向量存储封装 - 文档知识库

提供「写入向量」和「按向量检索」，与现有 EmbeddingClient 对接。
用于文档 chunk 的存储与语义检索，支持 metadata 过滤（如 user_id、source_file）。
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 默认集合名与持久化目录
DEFAULT_COLLECTION_NAME = "doc_chunks"
DEFAULT_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "")


def _default_persist_dir() -> str:
    if DEFAULT_PERSIST_DIR:
        return DEFAULT_PERSIST_DIR
    try:
        import config
        return str(getattr(config, "CHROMA_PERSIST_DIR", "") or (Path(config.DATA_DIR) / "chroma"))
    except Exception:
        return str(Path(__file__).resolve().parents[1] / "data" / "chroma")


class ChromaStore:
    """
    基于 Chroma 的向量存储，用于文档知识库的 chunk 写入与检索。

    - add(id, text, metadata): 写入单条
    - add_batch(ids, texts, metadatas): 批量写入
    - search(query_text, k, where): 按文本语义检索，支持 metadata 过滤（如 user_id）
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_client: Optional[Any] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        """
        Args:
            persist_directory: Chroma 持久化目录，默认 DATA_DIR/chroma 或 CHROMA_PERSIST_DIR
            embedding_client: 需实现 encode_single(text)->List[float], get_embeddings(texts)->List[List[float]]
            collection_name: 集合名
        """
        self._persist_dir = persist_directory or _default_persist_dir()
        self._collection_name = collection_name
        self._embedding = embedding_client

        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)

        import chromadb
        from chromadb.config import Settings

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaStore 初始化: persist_dir=%s, collection=%s", self._persist_dir, self._collection_name)

    def _get_embedding(self):
        if self._embedding is not None:
            return self._embedding
        try:
            from llm.client import EmbeddingClient
            self._embedding = EmbeddingClient()
            return self._embedding
        except Exception as e:
            logger.warning("ChromaStore 未传入 embedding_client 且自动创建失败: %s", e)
            raise RuntimeError("ChromaStore 需要 EmbeddingClient，请传入或确保 llm.client.EmbeddingClient 可用") from e

    def add(self, id: str, text: str, metadata: Dict[str, Any]) -> None:
        """
        写入单条 chunk。

        Args:
            id: 唯一 id（如 doc_id:chunk_index）
            text: 文本内容
            metadata: 如 user_id, source_file, doc_id, chunk_index, source_type
        """
        enc = self._get_embedding()
        emb = enc.encode_single(text) if hasattr(enc, "encode_single") else enc.get_embedding(text)
        # Chroma 的 metadata 值仅支持 str, int, float, bool
        meta = {k: v for k, v in (metadata or {}).items() if v is not None and isinstance(v, (str, int, float, bool))}

        self._collection.add(
            ids=[id],
            embeddings=[emb],
            documents=[text],
            metadatas=[meta],
        )

    def add_batch(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """批量写入。metadatas 与 ids/texts 一一对应。"""
        if not ids:
            return
        enc = self._get_embedding()
        if hasattr(enc, "get_embeddings"):
            embs = enc.get_embeddings(texts)
        else:
            embs = [enc.encode_single(t) if hasattr(enc, "encode_single") else enc.get_embedding(t) for t in texts]

        safe_meta = [
            {k: v for k, v in (m or {}).items() if v is not None and isinstance(v, (str, int, float, bool))}
            for m in metadatas
        ]

        self._collection.add(
            ids=ids,
            embeddings=embs,
            documents=texts,
            metadatas=safe_meta,
        )
        logger.info("ChromaStore add_batch: %d 条", len(ids))

    def search(
        self,
        query_text: str,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        按文本语义检索。

        Args:
            query_text: 查询文本
            k: 返回条数
            where: Chroma metadata 过滤，如 {"user_id": "xxx"} 或 {"$and": [{"user_id":"u1"}, {"source_type":"pdf"}]}

        Returns:
            [{"id", "text", "metadata", "distance"}, ...]，distance 为余弦距离（越小越相似）
        """
        enc = self._get_embedding()
        emb = enc.encode_single(query_text) if hasattr(enc, "encode_single") else enc.get_embedding(query_text)

        res = self._collection.query(
            query_embeddings=[emb],
            n_results=min(k, 100),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = res.get("ids") or [[]]
        docs = res.get("documents") or [[]]
        metas = res.get("metadatas") or [[]]
        dists = res.get("distances") or [[]]

        out = []
        for i, id_ in enumerate(ids[0] if ids else []):
            out.append({
                "id": id_,
                "text": (docs[0][i] if i < len(docs[0]) else "") if docs else "",
                "metadata": (metas[0][i] if i < len(metas[0]) else {}) if metas else {},
                "distance": (dists[0][i] if i < len(dists[0]) else 0.0) if dists else 0.0,
            })
        return out

    def get_chunks(
        self,
        where: Optional[Dict[str, Any]] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        按 where 条件获取 chunk 列表，用于文档列表聚合、删除前计数等。

        Args:
            where: Chroma metadata 过滤，如 {"doc_id": "x"} 或 {"user_id": "u1"}
            limit: 最多返回条数

        Returns:
            [{"id", "metadata"}, ...]，不包含 documents 以节省内存
        """
        res = self._collection.get(
            where=where,
            include=["metadatas"],
            limit=min(limit, 100000),
        )
        ids = res.get("ids") or []
        metas = res.get("metadatas") or [[]]
        return [
            {"id": ids[i], "metadata": metas[i] if i < len(metas) else {}}
            for i in range(len(ids))
        ]

    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> None:
        """
        按 id 列表或 where 条件删除。至少传 ids 或 where 之一。
        """
        if ids:
            self._collection.delete(ids=ids)
        if where is not None:
            self._collection.delete(where=where)
        if not ids and where is None:
            raise ValueError("delete 需要提供 ids 或 where")

    def count(self) -> int:
        """返回集合中的条目数（近似）。"""
        return self._collection.count()
