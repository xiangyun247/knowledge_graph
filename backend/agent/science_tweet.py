#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科普推文与多格式内容生成模块

- generate_science_tweet: 生成 1～3 条科普推文，可带话题标签
- generate_health_tip: 生成单条健康小贴士
- 复用 RAG 检索（图谱 + 文献），确保内容有依据
- Prompt 中控制长度、避免绝对化表述、加「仅供参考，具体请咨询医生」
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 科普推文 Prompt 模板
SCIENCE_TWEET_PROMPT = """你是一名擅长健康科普的医学编辑，负责将医学知识转化为适合社交媒体传播的短文案。

【写作目标】
- 为「{topic}」生成 1～3 条科普推文。
- 每条推文严格控制在 {word_limit} 字以内（含标点）。
- 风格要求：{style}。
- 语言：通俗、口语化、易传播，适合朋友圈/微博/公众号。

【可参考的医学要点】
下面是从知识图谱和医学文献中整理出的要点，请基于这些内容撰写，不要编造：

{context_block}

【写作规范】
1. 控制长度：每条不超过 {word_limit} 字。
2. 避免绝对化表述：不用「一定」「绝对」「必须」等，改用「建议」「可以」「通常」。
3. 结尾可加「仅供参考，具体请咨询医生」或类似提示。
4. 可适当使用 emoji 增加亲和力（1～2 个即可，不要过多）。

【输出格式】
请用 JSON 格式输出，不要添加多余解释。字段：
- tweets: 数组，每项为一条推文文案（string）。
- hashtags: 数组，建议的话题标签，如 ["#胰腺健康", "#科普"]，可选 0～5 个。

示例输出结构：
{{
  "tweets": [
    "急性胰腺炎出院后，饮食清淡、戒烟酒、按时复查很重要～具体请遵医嘱哦～",
    "慢性胰腺炎日常要注意少油少酒，定期复查，有不适及时就医。"
  ],
  "hashtags": ["#胰腺健康", "#科普", "#患者教育"]
}}

现在请根据以上要求生成 JSON："""

# 健康小贴士 Prompt
HEALTH_TIP_PROMPT = """你是一名健康科普编辑，负责生成单条健康小贴士。

【写作目标】
- 为「{topic}」生成 1 条健康小贴士。
- 控制在 80～140 字，简洁、实用、易记。
- 语气：温和、鼓励，避免恐吓。

【可参考的医学要点】
{context_block}

【写作规范】
1. 避免绝对化表述。
2. 结尾加「仅供参考，具体请咨询医生」。
3. 可加 1 个 emoji 增加亲和力。

【输出格式】
JSON：{{ "tip": "单条小贴士文案" }}

现在请生成 JSON："""


def _get_graph_context(topic: str, max_length: int = 2000) -> str:
    """从知识图谱检索与 topic 相关的上下文。"""
    try:
        from .tools import _graph_retriever_impl, _neo4j_client
        gr = _graph_retriever_impl()
        if gr is None:
            return ""
        nc = _neo4j_client()
        if not nc:
            return ""
        ents = nc.search_entities(topic, limit=5)
        names = [e.get("name") or "" for e in ents if e.get("name")]
        if not names:
            names = [topic.strip()[:20]]
        res = gr.retrieve(query=topic, entity_names=names, max_depth=2, limit=12)
        return gr.format_results_for_context(res, max_length=max_length)
    except Exception as e:
        logger.warning("科普推文-图检索失败: %s", e)
        return ""


def _get_doc_context(topic: str, k: int = 4) -> str:
    """从文档知识库检索与 topic 相关的文献片段。"""
    try:
        from .tools import _chroma_store
        from .context import get_agent_user_id
        cs = _chroma_store()
        if cs is None:
            return ""
        uid = get_agent_user_id()
        where = {"user_id": uid} if uid else None
        hits = cs.search(query_text=topic.strip(), k=k, where=where)
        if not hits:
            return ""
        lines = []
        for h in hits:
            meta = h.get("metadata") or {}
            src = meta.get("source_file", "未知")
            text = (h.get("text") or "")[:350]
            lines.append(f"[{src}]: {text}…")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("科普推文-文献检索失败: %s", e)
        return ""


def _call_llm(prompt: str, max_tokens: int = 800) -> str:
    """调用 LLM 生成内容。"""
    try:
        from llm.client import LLMClient
        client = LLMClient()
        messages = [
            {"role": "system", "content": "你是一个医疗科普写作助手，严格按照用户要求输出 JSON，不要输出任何其他文字。"},
            {"role": "user", "content": prompt},
        ]
        resp = client.chat(messages, temperature=0.6, max_tokens=max_tokens)
        return (resp or "").strip()
    except Exception as e:
        logger.error("科普推文-LLM 调用失败: %s", e)
        raise


def _parse_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """从 LLM 返回中解析 JSON。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def generate_science_tweet(
    topic: str,
    word_limit: int = 140,
    style: str = "轻松",
    source_content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    生成科普推文。

    Args:
        topic: 主题，如「急性胰腺炎出院后注意事项」
        word_limit: 每条推文字数限制，默认 140（微博风格），可选 280
        style: 风格，如「轻松」「严谨」「亲切」
        source_content: 可选，已有回答/文章内容，作为主要参考（减少 RAG 检索）

    Returns:
        {
            "tweets": [str, ...],
            "hashtags": [str, ...]
        }
        若解析失败则返回 {"error": str, "tweets": [], "hashtags": []}
    """
    if not topic or not topic.strip():
        return {"error": "主题不能为空", "tweets": [], "hashtags": []}

    topic = topic.strip()
    word_limit = max(80, min(500, int(word_limit)))
    style = (style or "轻松").strip()

    # 1. 收集上下文
    if source_content and source_content.strip():
        context_block = f"【用户已有回答/内容，请据此提炼推文】\n\n{source_content.strip()[:3000]}"
    else:
        graph_ctx = _get_graph_context(topic)
        doc_ctx = _get_doc_context(topic)
        parts = []
        if graph_ctx:
            parts.append("【来自知识图谱】\n" + graph_ctx)
        if doc_ctx:
            parts.append("【来自文献】\n" + doc_ctx)
        context_block = "\n\n".join(parts) if parts else "（暂无相关图谱或文献，请基于你的医学知识写出简洁、安全的科普推文，并注明「仅供参考，具体请咨询医生」）"

    # 2. 构建 Prompt
    prompt = SCIENCE_TWEET_PROMPT.format(
        topic=topic,
        word_limit=word_limit,
        style=style,
        context_block=context_block,
    )

    # 3. 调用 LLM
    try:
        raw = _call_llm(prompt)
    except Exception as e:
        return {"error": str(e), "tweets": [], "hashtags": []}

    # 4. 解析 JSON
    parsed = _parse_json_from_response(raw)
    if not parsed:
        return {
            "error": "JSON 解析失败",
            "tweets": [],
            "hashtags": [],
        }

    tweets = parsed.get("tweets") or []
    if not isinstance(tweets, list):
        tweets = []
    tweets = [str(t).strip() for t in tweets if t]

    hashtags = parsed.get("hashtags") or []
    if not isinstance(hashtags, list):
        hashtags = []
    hashtags = [str(h).strip() for h in hashtags if h]

    return {
        "tweets": tweets,
        "hashtags": hashtags,
    }


def generate_health_tip(topic: str) -> Dict[str, Any]:
    """
    生成单条健康小贴士。

    Args:
        topic: 主题

    Returns:
        {"tip": str} 或 {"error": str, "tip": ""}
    """
    if not topic or not topic.strip():
        return {"error": "主题不能为空", "tip": ""}

    topic = topic.strip()

    graph_ctx = _get_graph_context(topic, max_length=1500)
    doc_ctx = _get_doc_context(topic, k=3)
    parts = []
    if graph_ctx:
        parts.append("【来自知识图谱】\n" + graph_ctx)
    if doc_ctx:
        parts.append("【来自文献】\n" + doc_ctx)
    context_block = "\n\n".join(parts) if parts else "（暂无相关图谱或文献，请基于医学知识写出简洁、安全的健康小贴士）"

    prompt = HEALTH_TIP_PROMPT.format(topic=topic, context_block=context_block)

    try:
        raw = _call_llm(prompt, max_tokens=300)
    except Exception as e:
        return {"error": str(e), "tip": ""}

    parsed = _parse_json_from_response(raw)
    if not parsed:
        return {"error": "JSON 解析失败", "tip": ""}

    tip = str(parsed.get("tip") or "").strip()
    return {"tip": tip}
