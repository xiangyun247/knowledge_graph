#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键构建「官方老年认知/忆路康知识图谱」脚本

功能：
1. 读取若干本地 PDF（老年认知障碍/认知照护相关指南或科普）；
2. 复用现有 KnowledgeGraphBuilder + LLM，将文本抽取为实体与关系并写入 Neo4j；
3. 将所有实体/关系汇总成一张「合并图」，在 MySQL knowledge_graphs 中创建一条记录，并写入 graph_data；
4. 打印生成的 graph_id，供前端作为「默认图谱」使用。

注意：
- 本脚本假设在项目根目录下运行：python scripts/build_official_cognitive_graph.py
- 需已正确配置 Neo4j、LLM 相关环境变量（与正常构建图谱一致）。
- 请将 PDF_PATHS 中的路径改为您本地的老年认知障碍/照护相关 PDF 文件路径。
"""

import os
import sys
from typing import List, Dict, Any

from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import uuid

import config
from db.neo4j_client import Neo4jClient
from db.mysql_client import get_mysql_client
from kg.builder import KnowledgeGraphBuilder
from llm.client import LLMClient


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ===== 需要构建为官方图谱的 PDF 路径（请改为您本地的老年认知/照护相关 PDF） =====
PDF_PATHS: List[str] = [
    # 示例（请替换为实际路径）:
    # r"C:\path\to\轻度认知障碍诊疗指南.pdf",
    # r"C:\path\to\老年痴呆照护手册.pdf",
]

# M22：无 PDF 时使用的内置文本（2–3 段老年认知障碍/照护内容），用于演示或快速构建官方图谱
FALLBACK_TEXTS: List[str] = [
    "轻度认知障碍（MCI）是介于正常衰老与痴呆之间的阶段。常见表现包括记忆减退、执行功能下降、注意力不集中、定向力轻度受损。日常照护应注重规律作息、按时服药防漏服、防跌倒与走失，并尽量简化信息呈现以降低认知负荷。可进行的检查包括神经心理量表（如 MMSE、MoCA）、头颅 MRI 或 CT、血液生化。风险因素包括高龄、遗传、心血管危险因素。",
    "认知障碍老人服药时应核对药名与剂量，用温开水送服，按医嘱时间服用，并做简单记录；不要擅自停药或改量。防跌倒要点：家中保持通道畅通、地面防滑、光线充足、常用物品放在易取处；外出尽量有人陪同。防走失措施：佩戴写有姓名与家属电话的标识、使用定位设备或一键呼叫、与邻居或社区保持联系。",
    "复诊前应带齐病历本和近期检查单，列出近期症状或疑问，准备好当前用药清单，提前确认就诊时间与科室；家属尽量陪同。家属与认知障碍老人沟通时宜放慢语速、一次只说一件事、多用肯定与鼓励，避免一次给太多选项。",
]

# 这条图谱在 MySQL 里展示给哪个 user_id
DEFAULT_USER_ID = os.getenv("OFFICIAL_GRAPH_USER_ID", "default_user")


def extract_pdf_text(pdf_path: str) -> str:
    """使用 pdfplumber 读取 PDF 正文，失败时返回空字符串。"""
    try:
        import pdfplumber
    except ImportError as e:
        logger.error("缺少 pdfplumber 依赖，请先在后端环境安装：pip install pdfplumber")
        raise e

    if not os.path.isfile(pdf_path):
        logger.warning(f"PDF 文件不存在，跳过: {pdf_path}")
        return ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            texts = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    texts.append(t)
        full_text = "\n\n".join(texts).strip()
        logger.info(f"PDF 提取完成: {pdf_path}, 文本长度={len(full_text)}")
        return full_text
    except Exception as e:
        logger.error(f"读取 PDF 失败，跳过该文件: {pdf_path}, error={e}")
        return ""


def _collect_text_sources() -> List[tuple]:
    """
    收集要处理的文本来源：优先 PDF，若无则使用 FALLBACK_TEXTS。
    返回 [(source_label, text), ...]
    """
    out: List[tuple] = []
    valid_pdfs = [p for p in (PDF_PATHS or []) if p and os.path.isfile(p)]
    if valid_pdfs:
        for path in valid_pdfs:
            text = extract_pdf_text(path)
            if text:
                out.append((path, text))
    if not out and FALLBACK_TEXTS:
        for i, t in enumerate(FALLBACK_TEXTS):
            if (t or "").strip():
                out.append((f"builtin_cognitive_{i + 1}", t.strip()))
        logger.info("PDF_PATHS 未配置或文件不存在，使用内置认知照护文本（%d 段）构建官方图谱。", len(out))
    return out


def build_official_graph():
    """主流程：从多篇 PDF 或内置文本构建合并图，并在 Neo4j + MySQL 中登记官方图谱。"""
    logger.info("====== 开始构建官方老年认知/忆路康知识图谱 ======")

    sources = _collect_text_sources()
    if not sources:
        logger.warning(
            "PDF_PATHS 为空或文件不存在，且未配置 FALLBACK_TEXTS。请在脚本中配置老年认知障碍/照护相关 PDF 路径或使用内置文本后再运行。"
        )
        return

    # 1. 初始化 Neo4j 与 LLM、构建器、MySQL
    neo4j_client = Neo4jClient(
        uri=config.NEO4J_URI,
        user=config.NEO4J_USER,
        password=config.NEO4J_PASSWORD,
        database=config.NEO4J_DATABASE,
    )
    if not neo4j_client.verify_connection():
        raise RuntimeError("Neo4j 连接失败，请检查配置后重试")

    llm_client = LLMClient(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        model=config.DEEPSEEK_MODEL,
    )
    if not llm_client.verify_connection():
        raise RuntimeError("LLM 连接失败，请检查 DEEPSEEK_API_KEY / BASE_URL / MODEL 配置")

    kg_builder = KnowledgeGraphBuilder(neo4j_client=neo4j_client, llm_client=llm_client)
    mysql_client = get_mysql_client()

    # 2. 逐篇 PDF 读取正文并调用构建器，累积实体/关系
    all_entities: List[Dict[str, Any]] = []
    all_relations: List[Dict[str, Any]] = []
    seen_entities = set()
    seen_relations = set()

    total_entities_created = 0
    total_relations_created = 0

    for source_label, text in sources:
        if not text:
            logger.warning(f"文本为空，跳过: {source_label}")
            continue

        logger.info(f"开始处理：{source_label}")
        result = kg_builder.process_text(text)

        ents = result.get("entities", []) or []
        rels = result.get("relations", []) or []
        total_entities_created += result.get("entities_created", 0) or 0
        total_relations_created += result.get("relations_created", 0) or 0

        for e in ents:
            key = (e.get("name"), e.get("type"))
            if not key[0] or key in seen_entities:
                continue
            seen_entities.add(key)
            all_entities.append(e)

        for r in rels:
            key = (r.get("subject"), r.get("predicate"), r.get("object"))
            if not key[0] or not key[2] or key in seen_relations:
                continue
            seen_relations.add(key)
            all_relations.append(r)

    logger.info(
        f"全部来源处理完成：Neo4j 中创建实体约 {total_entities_created} 个，关系约 {total_relations_created} 条；"
        f"去重后实体 {len(all_entities)} 个，关系 {len(all_relations)} 条。"
    )

    if not all_entities and not all_relations:
        logger.error("未得到任何实体或关系，终止。请检查 PDF 内容与 LLM 配置。")
        return

    # 3. 在 MySQL knowledge_graphs 中创建一条官方图谱记录，并写入 graph_data 快照
    graph_name = "官方忆路康/老年认知照护知识图谱（内置）"
    description = "基于老年认知障碍/认知照护相关文献，通过 LLM 抽取实体与关系并合并形成的官方图谱"
    valid_pdfs = [p for p in (PDF_PATHS or []) if p and os.path.isfile(p)]
    data_source = "official_cognitive_care_pdfs" if valid_pdfs else "official_cognitive_care_builtin"
    file_path = ";".join(valid_pdfs) if valid_pdfs else ";".join([s[0] for s in sources])
    user_id = DEFAULT_USER_ID or "default_user"

    logger.info(f"开始在 MySQL 中创建官方图谱记录，user_id={user_id!r}")

    from db.mysql_client import MySQLClient as SAClient  # type: ignore

    graph_id = mysql_client.create_graph(
        graph_name=graph_name,
        description=description,
        data_source=data_source,
        file_path=file_path,
        user_id=user_id,
    )

    mysql_client.update_graph_status(
        graph_id=graph_id,
        status="completed",
        entity_count=len(all_entities),
        relation_count=len(all_relations),
    )

    nodes_for_db: List[Dict[str, Any]] = []
    seen_node_names = set()
    for e in all_entities:
        name = (e.get("name") or "").strip()
        if not name or name in seen_node_names:
            continue
        seen_node_names.add(name)
        etype = (e.get("type") or "entity").strip()
        nodes_for_db.append(
            {
                "id": name,
                "name": name,
                "type": etype,
                "category": etype.lower(),
                "description": (e.get("description") or "").strip(),
            }
        )

    relations_for_db: List[Dict[str, Any]] = []
    seen_edge_ids = set()
    for r in all_relations:
        sub = (r.get("subject") or "").strip()
        pred = (r.get("predicate") or "").strip()
        obj = (r.get("object") or "").strip()
        if not sub or not obj:
            continue
        edge_id = f"{sub}_{pred}_{obj}"
        if edge_id in seen_edge_ids:
            continue
        seen_edge_ids.add(edge_id)
        relations_for_db.append(
            {
                "id": edge_id,
                "source": sub,
                "target": obj,
                "relation": pred,
            }
        )

    mysql_client.update_graph_data(
        graph_id,
        {"nodes": nodes_for_db, "relations": relations_for_db},
    )

    logger.info("====== 官方老年认知/忆路康知识图谱构建完成 ======")
    logger.info(f"graph_id = {graph_id}")
    logger.info(f"去重后节点数 = {len(nodes_for_db)}, 关系数 = {len(relations_for_db)}")
    logger.info(
        "你可以在前端中，将图谱列表默认选中这条记录（graph_id），或在 /api/graph/data 不传 graph_id 时优先加载它。"
    )


if __name__ == "__main__":
    build_official_graph()
