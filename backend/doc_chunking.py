#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档分块与元数据设计 - 文档知识库

- Chunk 元数据 schema：doc_id, chunk_index, source_file, source_type, user_id 等
- 分块策略：paragraph（按段）、fixed（固定长度+重叠）、smart（尽量在句界切分）
"""

import re
import logging
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# -------------------- 元数据 schema（与 Chroma metadata 兼容：str/int/float/bool）--------------------

def chunk_metadata(
    doc_id: str,
    chunk_index: int,
    source_file: str,
    source_type: str = "txt",
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构建单条 chunk 的 metadata，仅包含 Chroma 支持的 str/int/float/bool。

    Args:
        doc_id: 文档唯一 id
        chunk_index: 块序号，从 0 起
        source_file: 来源文件名
        source_type: 如 txt, pdf, json
        user_id: 用户 id，用于「我的知识库」过滤
        extra: 其它字段，只保留 str/int/float/bool

    Returns:
        可直接用于 ChromaStore.add(metadata=...) 的字典
    """
    meta: Dict[str, Any] = {
        "doc_id": str(doc_id),
        "chunk_index": int(chunk_index),
        "source_file": str(source_file),
        "source_type": str(source_type),
    }
    if user_id is not None:
        meta["user_id"] = str(user_id)
    if extra:
        for k, v in extra.items():
            if v is not None and isinstance(v, (str, int, float, bool)):
                meta[k] = v
    return meta


# -------------------- 分块策略 --------------------

def chunk_by_paragraph(text: str) -> List[str]:
    """按空行（\\n\\n 或更多）分块，保留非空块。"""
    if not (text or isinstance(text, str)):
        return []
    blocks = re.split(r'\n\s*\n+', text.strip())
    return [b.strip() for b in blocks if b and len(b.strip()) > 0]


def chunk_by_fixed(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    按固定长度分块，相邻块有 overlap 字符重叠，避免割裂语义。
    """
    if not (text or isinstance(text, str)) or chunk_size <= 0:
        return []
    text = text.strip()
    if not text:
        return []
    overlap = max(0, min(chunk_overlap, chunk_size - 1))
    step = chunk_size - overlap
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += step
    return chunks


def _sentence_boundaries(text: str) -> List[Tuple[int, int]]:
    """返回句子在 text 中的 (start, end) 列表。按中文。！？及英文 .!? 和换行切分。"""
    if not text:
        return []
    # 按句末标点或 \n 切，保留分隔符到前一句
    pattern = r'[。！？\.\?!\n]+'
    spans = []
    last = 0
    for m in re.finditer(pattern, text):
        end = m.end()
        spans.append((last, end))
        last = end
    if last < len(text):
        spans.append((last, len(text)))
    return [(s, e) for s, e in spans if e > s and text[s:e].strip()]


def chunk_smart(
    text: str,
    max_chunk_size: int = 1000,
    overlap_sentences: int = 1,
) -> List[str]:
    """
    在句子边界处切分，使每块不超过 max_chunk_size，且尽量不截断句子。
    overlap_sentences：块之间重叠的句子数，0 表示不重叠。
    """
    if not (text or isinstance(text, str)) or max_chunk_size <= 0:
        return []
    text = text.strip()
    if not text:
        return []
    spans = _sentence_boundaries(text)
    if not spans:
        return chunk_by_fixed(text, chunk_size=max_chunk_size, chunk_overlap=min(100, max_chunk_size // 5))

    chunks = []
    i = 0
    while i < len(spans):
        current = []
        size = 0
        j = i
        while j < len(spans):
            s, e = spans[j]
            seg = text[s:e]
            add = len(seg)
            if size + add > max_chunk_size and current:
                break
            current.append(seg)
            size += add
            j += 1
        if current:
            chunks.append("".join(current).strip())
        # 下一块起点：回退 overlap_sentences 句，避免完全割裂
        if overlap_sentences > 0 and j > i:
            i = max(i + 1, j - overlap_sentences)
        else:
            i = j
    return [c for c in chunks if c]


# -------------------- 统一入口 --------------------

def chunk_text(
    text: str,
    doc_id: str,
    source_file: str,
    source_type: str = "txt",
    user_id: Optional[str] = None,
    strategy: str = "fixed",
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    max_chunk_size: int = 1000,
    overlap_sentences: int = 1,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    对文本分块，并生成每条对应的 metadata。

    Args:
        text: 原始文本
        doc_id: 文档 id
        source_file: 文件名
        source_type: txt / pdf / json 等
        user_id: 用户 id，可选
        strategy: "paragraph" | "fixed" | "smart"
        chunk_size: fixed 策略的块长
        chunk_overlap: fixed 策略的重叠长
        max_chunk_size: smart 策略的最大块长
        overlap_sentences: smart 策略的句重叠数
        extra_meta: 写入每条 metadata 的额外字段（仅 str/int/float/bool）

    Returns:
        [(chunk_text, metadata), ...]，metadata 可直接给 ChromaStore.add(id=..., text=chunk_text, metadata=metadata)
    """
    if not (text and isinstance(text, str)):
        return []

    if strategy == "paragraph":
        raw = chunk_by_paragraph(text)
    elif strategy == "smart":
        raw = chunk_smart(text, max_chunk_size=max_chunk_size, overlap_sentences=overlap_sentences)
    else:
        raw = chunk_by_fixed(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    out: List[Tuple[str, Dict[str, Any]]] = []
    for idx, t in enumerate(raw):
        if not t or not t.strip():
            continue
        meta = chunk_metadata(
            doc_id=doc_id,
            chunk_index=idx,
            source_file=source_file,
            source_type=source_type,
            user_id=user_id,
            extra=extra_meta,
        )
        out.append((t.strip(), meta))
    return out


def chunk_id(doc_id: str, chunk_index: int) -> str:
    """生成 Chroma 用的 chunk 唯一 id。"""
    return f"{doc_id}:{chunk_index}"
