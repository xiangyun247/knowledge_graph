#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档知识库API路由
"""

import os
import uuid
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Body, Query
from pydantic import BaseModel
from starlette.responses import JSONResponse

from backend.auth import get_current_user_id, require_roles
from backend.text_clean import clean_medical_text
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/kb", tags=["文档知识库"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


class CreateKbBody(BaseModel):
    name: str
    description: Optional[str] = ""


class RenameKbBody(BaseModel):
    name: str


class KbAskBody(BaseModel):
    question: str
    kb_id: Optional[str] = None


class ReindexRequest(BaseModel):
    kb_id: str
    doc_ids: Optional[List[str]] = None


knowledge_bases: Dict[str, Dict[str, Any]] = {}
DEFAULT_KB_ID = "default"
DEFAULT_KB_NAME = "我的知识库"


def _ensure_knowledge_bases_table():
    mysql = get_mysql()
    if not mysql:
        return
    try:
        mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS knowledge_bases (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                description TEXT,
                user_id VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception as e:
        logger.warning(f"创建knowledge_bases表失败: {e}")


def _get_chroma_store():
    from backend.chroma_store import get_chroma_store
    return get_chroma_store()


@router.get("/bases")
async def list_kb_bases(request: Request):
    """获取知识库列表"""
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    if mysql:
        try:
            _ensure_knowledge_bases_table()
            result = mysql.execute_query(
                "SELECT * FROM knowledge_bases WHERE user_id = :user_id OR user_id IS NULL",
                {"user_id": user_id}
            )
            return {"status": "success", "data": result or []}
        except Exception as e:
            logger.error(f"获取知识库列表失败: {e}")

    return {"status": "success", "data": [{"id": DEFAULT_KB_ID, "name": DEFAULT_KB_NAME}]}


@router.post("/bases")
async def create_kb_base(request: Request, body: CreateKbBody):
    """创建知识库"""
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    kb_id = str(uuid.uuid4())

    if mysql:
        try:
            _ensure_knowledge_bases_table()
            mysql.execute_update(
                "INSERT INTO knowledge_bases (id, name, description, user_id) VALUES (:id, :name, :desc, :uid)",
                {"id": kb_id, "name": body.name, "desc": body.description or "", "uid": user_id}
            )
        except Exception as e:
            logger.error(f"创建知识库失败: {e}")

    return {"status": "success", "id": kb_id, "name": body.name}


@router.patch("/bases/{kb_id}")
async def rename_kb_base(request: Request, kb_id: str, body: RenameKbBody):
    """重命名知识库"""
    mysql = get_mysql()

    if mysql:
        try:
            mysql.execute_update(
                "UPDATE knowledge_bases SET name = :name WHERE id = :id",
                {"id": kb_id, "name": body.name}
            )
        except Exception as e:
            logger.warning(f"重命名知识库失败: {e}")

    return {"status": "success"}


@router.post("/documents/ingest")
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    kb_id: str = Query(DEFAULT_KB_ID),
    chunk_size: int = Query(500, ge=100, le=2000),
    overlap: int = Query(50, ge=0, le=200)
):
    """上传并索引文档"""
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    try:
        contents = await file.read()
        text = contents.decode("utf-8", errors="ignore")

        if len(text) < 50:
            return {"status": "error", "message": "文档内容太少"}

        cleaned = clean_medical_text(text)

        doc_id = str(uuid.uuid4())
        store = _get_chroma_store()

        try:
            store.add_texts(
                texts=[cleaned],
                metadatas=[{"kb_id": kb_id, "user_id": user_id, "file_name": file.filename}],
                ids=[doc_id]
            )
        except Exception as e:
            logger.warning(f"Chroma存储失败: {e}")

        if mysql:
            try:
                mysql.execute_update(
                    """INSERT INTO kb_documents (id, kb_id, file_name, content, user_id)
                       VALUES (:id, :kb_id, :filename, :content, :uid)""",
                    {"id": doc_id, "kb_id": kb_id, "filename": file.filename, "content": cleaned[:10000], "uid": user_id}
                )
            except Exception as e:
                logger.warning(f"MySQL保存文档失败: {e}")

        return {"status": "success", "doc_id": doc_id, "chunks": 1}

    except Exception as e:
        logger.error(f"文档摄入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/search")
async def search_documents(
    request: Request,
    query: str = Query(..., min_length=1),
    kb_id: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20)
):
    """搜索文档"""
    user_id = get_current_user_id(request)

    try:
        store = _get_chroma_store()
        where_filter = {"user_id": user_id}
        if kb_id:
            where_filter["kb_id"] = kb_id

        try:
            results = store.search(query, n_results=top_k, where_filter=where_filter)
        except:
            results = {"documents": [], "distances": []}

        documents = []
        for i, doc in enumerate(results.get("documents", [])):
            documents.append({
                "content": doc,
                "distance": results.get("distances", [0])[i] if i < len(results.get("distances", [])) else 0,
                "metadata": results.get("metadatas", [{}])[i] if i < len(results.get("metadatas", [])) else {}
            })

        return {"status": "success", "data": {"documents": documents, "query": query}}

    except Exception as e:
        logger.error(f"文档搜索失败: {e}")
        return {"status": "success", "data": {"documents": [], "query": query}}


@router.get("/documents/list")
async def list_documents(
    request: Request,
    kb_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """获取文档列表"""
    user_id = get_current_user_id(request)
    mysql = get_mysql()

    if not mysql:
        return {"status": "success", "data": {"list": [], "total": 0}}

    try:
        if kb_id:
            result = mysql.execute_query(
                "SELECT id, kb_id, file_name, created_at FROM kb_documents WHERE kb_id = :kb_id AND user_id = :uid LIMIT :limit OFFSET :offset",
                {"kb_id": kb_id, "uid": user_id, "limit": limit, "offset": offset}
            )
        else:
            result = mysql.execute_query(
                "SELECT id, kb_id, file_name, created_at FROM kb_documents WHERE user_id = :uid LIMIT :limit OFFSET :offset",
                {"uid": user_id, "limit": limit, "offset": offset}
            )

        return {"status": "success", "data": {"list": result or [], "total": len(result or [])}}

    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        return {"status": "success", "data": {"list": [], "total": 0}}


@router.delete("/documents/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    """删除文档"""
    mysql = get_mysql()

    if mysql:
        try:
            mysql.execute_update("DELETE FROM kb_documents WHERE id = :id", {"id": doc_id})
        except Exception as e:
            logger.warning(f"删除文档失败: {e}")

    return {"status": "success"}


@router.post("/documents/reindex")
async def reindex_document(request: Request, body: ReindexRequest):
    """重新索引文档"""
    return {"status": "success", "message": "reindex not fully implemented"}
