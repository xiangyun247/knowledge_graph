#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键构建「官方胰腺炎知识图谱」脚本

功能：
1. 读取若干本地 PDF（胰腺炎指南/共识）；
2. 复用现有 KnowledgeGraphBuilder + LLM，将文本抽取为实体与关系并写入 Neo4j；
3. 将所有实体/关系汇总成一张「合并图」，在 MySQL knowledge_graphs 中创建一条记录，并写入 graph_data；
4. 打印生成的 graph_id，供前端作为「默认图谱」使用。

注意：
- 本脚本假设在项目根目录下运行：python scripts/build_official_pancreatitis_graph.py
- 需已正确配置 Neo4j、LLM 相关环境变量（与正常构建图谱一致）。
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


# ===== 需要构建为官方图谱的 PDF 路径（按你提供的绝对路径） =====
PDF_PATHS: List[str] = [
    r"C:\Users\23035\Desktop\胰腺炎1.pdf",
    r"C:\Users\23035\Desktop\胰腺炎2.pdf",
    r"C:\Users\23035\Desktop\急性胰腺炎急诊诊断及治疗专家共识.pdf",
    r"C:\Users\23035\Desktop\急性胰腺炎基层诊疗指南（实践版·2019）.pdf",
]

# 这条图谱在 MySQL 里展示给哪个 user_id
# 建议：将 OFFICIAL_GRAPH_USER_ID 设置成你打算登录前端的那个用户的 user_id（users 表里的 user_id）
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


def build_official_graph():
    """主流程：从多篇 PDF 构建合并图，并在 Neo4j + MySQL 中登记官方图谱。"""
    logger.info("====== 开始构建官方胰腺炎知识图谱 ======")

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

    for path in PDF_PATHS:
        text = extract_pdf_text(path)
        if not text:
            logger.warning(f"文件内容为空或提取失败，跳过: {path}")
            continue

        logger.info(f"开始处理：{path}")
        result = kg_builder.process_text(text)

        # builder.process_text 已将实体/关系写入 Neo4j，这里用于统计与 MySQL 快照
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
        f"全部 PDF 处理完成：Neo4j 中创建实体约 {total_entities_created} 个，关系约 {total_relations_created} 条；"
        f"去重后实体 {len(all_entities)} 个，关系 {len(all_relations)} 条。"
    )

    if not all_entities and not all_relations:
        logger.error("未得到任何实体或关系，终止。请检查 PDF 内容与 LLM 配置。")
        return

    # 3. 在 MySQL knowledge_graphs 中创建一条官方图谱记录，并写入 graph_data 快照
    graph_name = "官方胰腺炎知识图谱（内置）"
    description = "基于 3-5 篇胰腺炎指南/共识文献，通过 LLM 抽取实体与关系并合并形成的官方图谱"
    data_source = "official_pancreatitis_pdfs"
    file_path = ";".join(PDF_PATHS)
    user_id = DEFAULT_USER_ID or "default_user"

    logger.info(f"开始在 MySQL 中创建官方图谱记录，user_id={user_id!r}")

    from db.mysql_client import MySQLClient as SAClient  # type: ignore

    # db.mysql_client 的 create_graph 返回 graph_id（UUID 字符串）
    graph_id = mysql_client.create_graph(
        graph_name=graph_name,
        description=description,
        data_source=data_source,
        file_path=file_path,
        user_id=user_id,
    )

    # 更新状态与计数
    mysql_client.update_graph_status(
        graph_id=graph_id,
        status="completed",
        entity_count=len(all_entities),
        relation_count=len(all_relations),
    )

    # 将实体/关系转换为前端期望的 nodes / relations 结构
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

    logger.info("====== 官方胰腺炎知识图谱构建完成 ======")
    logger.info(f"graph_id = {graph_id}")
    logger.info(f"去重后节点数 = {len(nodes_for_db)}, 关系数 = {len(relations_for_db)}")
    logger.info(
        "你可以在前端中，将图谱列表默认选中这条记录（graph_id），或在 /api/graph/data 不传 graph_id 时优先加载它。"
    )


if __name__ == "__main__":
    build_official_graph()

