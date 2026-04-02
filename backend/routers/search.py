#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索API路由
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Query

from backend.auth import get_current_user_id
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/search", tags=["搜索"])


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


neo4j_client = None
try:
    from db.neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient()
except Exception as e:
    logger.warning(f"Neo4j客户端初始化失败: {e}")


def _ensure_neo4j_client():
    global neo4j_client
    if neo4j_client is None:
        try:
            neo4j_client = Neo4jClient()
        except:
            pass
    return neo4j_client


@router.get("/entities")
async def search_entities(
    request: Request,
    keyword: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    exact_match: bool = Query(False)
):
    """搜索实体"""
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    results = []

    if mysql:
        try:
            pattern = f"%{keyword}%"
            result = mysql.execute_query(
                """SELECT id, name, type, properties
                   FROM kg_nodes
                   WHERE name LIKE :pattern
                   LIMIT :limit""",
                {"pattern": pattern, "limit": limit}
            )
            results = result or []
        except Exception as e:
            logger.warning(f"MySQL实体搜索失败: {e}")

    if not results and _ensure_neo4j_client():
        try:
            cypher = """
                MATCH (n)
                WHERE n.name CONTAINS $keyword
                RETURN n.name as name, labels(n)[0] as type, properties(n) as properties
                LIMIT $limit
            """
            result = neo4j_client.execute_query(cypher, {"keyword": keyword, "limit": limit})
            results = [{"id": r["name"], "name": r["name"], "type": r.get("type", "Entity")} for r in result]
        except Exception as e:
            logger.warning(f"Neo4j实体搜索失败: {e}")

    return {"status": "success", "data": results, "keyword": keyword}


@router.get("/relations")
async def search_relations(
    request: Request,
    keyword: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100)
):
    """搜索关系"""
    mysql = get_mysql()

    results = []

    if mysql:
        try:
            pattern = f"%{keyword}%"
            result = mysql.execute_query(
                """SELECT id, source, target, relation_type, properties
                   FROM kg_relations
                   WHERE relation_type LIKE :pattern
                   LIMIT :limit""",
                {"pattern": pattern, "limit": limit}
            )
            results = result or []
        except Exception as e:
            logger.warning(f"MySQL关系搜索失败: {e}")

    return {"status": "success", "data": results, "keyword": keyword}
