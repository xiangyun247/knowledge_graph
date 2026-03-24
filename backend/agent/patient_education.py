#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者教育内容生成模块

- generate_patient_education: 核心函数，基于图谱+文献检索生成患者教育短文
- 输出结构：{title, sections: [{heading, content}], summary}
- 内容规范参考 UpToDate 患者教育：通俗、短句、少术语、温和鼓励
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 患者教育 Prompt 模板（参考 UpToDate 患者教育风格，M19：认知照护侧重点）
PATIENT_EDUCATION_PROMPT = """你是一名擅长用通俗语言向老年患者及照护者解释疾病的医生，侧重认知照护与低认知负荷表达。

【写作目标】
- 为「{topic}」写一篇中文患者教育短文。
- 读者是老年患者及家属/照护者，希望了解病情和自我管理。
- 语言要求：通俗、短句、尽量少用专业术语；如必须使用，请在括号中简单解释。
- 语气要求：温和、鼓励，避免夸大风险或引起恐慌。
- 字数建议：800~1200 字左右；每段控制在 80 字以内，每条只讲一个要点；可自然拆成「第一步…第二步…」便于分步阅读。
- 优先覆盖认知照护高频主题：服药提醒、复诊准备、日常安全（防跌倒/防走失）、记忆与病情简述、家属沟通要点等。

【结构要求】
请严格按照以下结构组织内容：
1. 这是什么病？（或：这是在讲什么问题？）
2. 常见症状/表现
3. 什么时候需要尽快就医或联系医生
4. 日常注意事项与自我管理（如饮食、休息、用药、复查等；可拆成第一步、第二步…）
5. 温馨提示（用1~2句话做结尾，安抚和鼓励）

【可参考的医学要点】
下面是从知识图谱和医学文献中整理出的要点，请在保证准确性的前提下，
用自己的话重写成患者能看懂的内容，不要逐字照抄：

{context_block}

【额外输出：分享文案】
请同时为社交媒体（如朋友圈/公众号）写一段 80~200 字的简短分享文案，用非常口语、轻松、安抚的语气，概括最关键的 2~3 个提醒点。
这段文案面向普通患者或家属阅读，用来配合分享这篇患者教育文章。

【格式要求】
- 正文中不要使用 Markdown 符号（如 *、**、# 等），不要用星号表示强调或列表。
- 纯文字输出，直接写内容即可。

【输出格式】
请用 JSON 格式输出，不要添加多余解释。字段：
- title: string，整篇文章的标题。
- sections: 数组，每个元素包含：
    - heading: 小节标题
    - content: 小节正文（可分段，用换行符分段）
- summary: string，结尾的温馨提示。
- share_text: string，一段适合分享的简短文案。

示例输出结构（内容仅为示例）：
{{
  "title": "急性胰腺炎出院后护理指南",
  "sections": [
    {{"heading": "一、这是什么病？", "content": "急性胰腺炎是……"}},
    {{"heading": "二、常见症状和表现", "content": "……"}}
  ],
  "summary": "请遵医嘱，出现不适及时就医。",
  "share_text": "急性胰腺炎出院后，饮食清淡、戒烟酒、按时复查特别重要。这篇小指南用通俗的语言帮你梳理出院后的几件大事，希望能陪你一起安心康复。"
}}

现在请根据以上要求生成 JSON："""


def _get_graph_context(topic: str, max_length: int = 2500) -> str:
    """从知识图谱检索与 topic 相关的上下文。"""
    try:
        from .tools import _graph_retriever_impl, _neo4j_client
        gr = _graph_retriever_impl()
        if gr is None:
            return ""
        nc = _neo4j_client()
        if not nc:
            return ""
        # 从 topic 中提取实体名（简单：用 Neo4j search_entities）
        ents = nc.search_entities(topic, limit=5)
        names = [e.get("name") or "" for e in ents if e.get("name")]
        if not names:
            # M20：无命中时用认知照护相关词再试，使患者教育默认更贴照护场景
            for fallback_term in ("认知障碍", "照护", "服药"):
                ents = nc.search_entities(fallback_term, limit=2)
                names.extend([e.get("name") or "" for e in ents if e.get("name")])
            names = list(dict.fromkeys(n for n in names if n))[:5]
        if not names:
            names = [topic.strip()[:20]]  # 回退：用 topic 前段作为检索词
        res = gr.retrieve(query=topic, entity_names=names, max_depth=2, limit=15)
        return gr.format_results_for_context(res, max_length=max_length)
    except Exception as e:
        logger.warning("患者教育-图检索失败: %s", e)
        return ""


def _get_doc_context(topic: str, k: int = 5) -> str:
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
            text = (h.get("text") or "")[:400]
            lines.append(f"[{src}]: {text}…")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("患者教育-文献检索失败: %s", e)
        return ""


def _call_llm(prompt: str) -> str:
    """调用 LLM 生成患者教育内容。"""
    try:
        from llm.client import LLMClient
        client = LLMClient()
        messages = [
            {"role": "system", "content": "你是一个医疗写作助手，严格按照用户要求输出 JSON，不要输出任何其他文字。"},
            {"role": "user", "content": prompt},
        ]
        resp = client.chat(messages, temperature=0.5, max_tokens=2500)
        return (resp or "").strip()
    except Exception as e:
        logger.error("患者教育-LLM 调用失败: %s", e)
        raise


def _parse_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """从 LLM 返回中解析 JSON。"""
    if not text:
        return None
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试提取 { ... } 块
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _strip_asterisks(text: str) -> str:
    """移除文本中的星号（Markdown 加粗/斜体等）。"""
    if not text:
        return ""
    # 先去掉 **粗体** 和 *斜体*，再去掉残留的 *
    s = str(text)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)  # **text** -> text
    s = re.sub(r"\*([^*]*)\*", r"\1", s)      # *text* -> text
    s = s.replace("*", "")                       # 剩余 * 全部去掉
    return s.strip()


# 分步版规范：每步一句短句，可选配图说明；最多 5–7 步；每步字数上限 30 字（便于低认知负荷「一次只显示一步」）
STEP_MAX_COUNT = 7
STEP_MAX_CHARS = 30


def _derive_steps_from_sections(sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """从 sections 派生出分步列表：每步一句短句、最多 STEP_MAX_COUNT 步、每步最多 STEP_MAX_CHARS 字。"""
    steps: List[Dict[str, str]] = []
    for sec in (sections or []):
        heading = (sec.get("heading") or "").strip()
        content = (sec.get("content") or "").strip()
        # 按句切分：。！？；\n
        raw_sentences = re.split(r"[。！？；\n]+", content)
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            # 若过长则按 STEP_MAX_CHARS 截断为多步
            while len(s) > STEP_MAX_CHARS:
                steps.append({"text": s[:STEP_MAX_CHARS].strip(), "image_caption": ""})
                s = s[STEP_MAX_CHARS:].strip()
            if s:
                steps.append({"text": s, "image_caption": ""})
            if len(steps) >= STEP_MAX_COUNT:
                return steps
        if heading and len(steps) < STEP_MAX_COUNT:
            short = heading if len(heading) <= STEP_MAX_CHARS else heading[:STEP_MAX_CHARS]
            if short not in [x.get("text") for x in steps]:
                steps.append({"text": short, "image_caption": ""})
            if len(steps) >= STEP_MAX_COUNT:
                return steps
    return steps[:STEP_MAX_COUNT]


def _derive_cards_from_sections(sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """从 sections 派生出卡片列表：每小节对应一张卡片，大字号/高对比度展示用。"""
    cards: List[Dict[str, str]] = []
    for sec in (sections or []):
        cards.append({
            "title": (sec.get("heading") or "").strip(),
            "content": (sec.get("content") or "").strip(),
        })
    return cards


def generate_patient_education(
    topic: str,
    context_snippets: Optional[List[str]] = None,
    language: str = "zh",
) -> Dict[str, Any]:
    """
    生成患者教育短文。

    Args:
        topic: 主题，如「急性胰腺炎出院后注意事项」
        context_snippets: 可选，外部传入的上下文片段（若为空则内部检索）
        language: 语言，默认 zh

    Returns:
        {
            "title": str,
            "sections": [{"heading": str, "content": str}, ...],
            "summary": str
        }
        若解析失败则返回 {"error": str, "raw": str}
    """
    if not topic or not topic.strip():
        return {"error": "主题不能为空", "raw": ""}

    topic = topic.strip()

    # 1. 收集上下文
    if context_snippets:
        context_block = "\n\n".join(context_snippets)
    else:
        graph_ctx = _get_graph_context(topic)
        doc_ctx = _get_doc_context(topic)
        parts = []
        if graph_ctx:
            parts.append("【来自知识图谱】\n" + graph_ctx)
        if doc_ctx:
            parts.append("【来自文献】\n" + doc_ctx)
        context_block = "\n\n".join(parts) if parts else "（暂无相关图谱或文献，请基于你的医学知识写出通俗、安全的患者教育内容，并注明「仅供参考，具体请遵医嘱」）"

    # 2. 构建 Prompt
    prompt = PATIENT_EDUCATION_PROMPT.format(
        topic=topic,
        context_block=context_block,
    )

    # 3. 调用 LLM
    try:
        raw = _call_llm(prompt)
    except Exception as e:
        return {"error": str(e), "raw": "", "title": "", "sections": [], "summary": ""}

    # 4. 解析 JSON
    parsed = _parse_json_from_response(raw)
    if not parsed:
        return {
            "error": "JSON 解析失败",
            "raw": raw[:2000],
            "title": topic,
            "sections": [],
            "summary": "",
        }

    # 5. 规范化输出，并移除星号等 Markdown 符号
    title = _strip_asterisks(parsed.get("title") or topic)
    sections = parsed.get("sections") or []
    if not isinstance(sections, list):
        sections = []
    out_sections = []
    for s in sections:
        if isinstance(s, dict):
            h = _strip_asterisks(s.get("heading") or "")
            c = _strip_asterisks(s.get("content") or "")
            out_sections.append({"heading": h, "content": c})
    summary = _strip_asterisks(parsed.get("summary") or "")
    share_text = _strip_asterisks(parsed.get("share_text") or "")

    # 知识装饰：同一内容多形态呈现（M6/M7）
    steps = _derive_steps_from_sections(out_sections)
    cards = _derive_cards_from_sections(out_sections)

    return {
        "title": str(title),
        "sections": out_sections,
        "summary": str(summary),
        "share_text": str(share_text),
        "steps": steps,
        "cards": cards,
    }
