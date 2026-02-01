#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱系统后端API
"""

import os
import sys
import tempfile
# 将项目根目录添加到Python路径中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_ROOT)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
import uuid
import threading
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Request, Body
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from db.mysql_client import get_mysql_client
from backend.auth import get_current_user_id
import hashlib

# 尝试导入 Neo4j 客户端（可选，用于实体搜索）
neo4j_client = None
try:
    from db.neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient()
    if neo4j_client.verify_connection():
        logger.info("Neo4j客户端初始化成功，实体搜索将使用Neo4j")
    else:
        neo4j_client = None
        logger.warning("Neo4j连接验证失败，实体搜索将回退到MySQL")
except Exception as e:
    logger.warning(f"Neo4j客户端初始化失败: {e}，实体搜索将使用MySQL")

# 创建FastAPI应用
app = FastAPI(
    title="知识图谱系统API",
    description="知识图谱系统后端API接口文档",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# 初始化日志配置
logger.add(
    "logs/app.log",
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8"
)

# 初始化MySQL客户端（延迟加载）
mysql_client = None
try:
    mysql_client = get_mysql_client()
    logger.info("MySQL客户端初始化成功")
except Exception as e:
    logger.error(f"MySQL客户端初始化失败: {e}")
    logger.warning("应用将在没有MySQL的情况下运行，部分功能可能不可用（包括注册/登录）")


# ==================== 简单用户与认证相关工具 ====================

def _ensure_users_table() -> None:
    """确保存在 users 表，用于简单用户名/密码登录。"""
    if not mysql_client:
        return
    create_sql = """
    CREATE TABLE IF NOT EXISTS users (
        user_id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(255),
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    mysql_client.execute_update(create_sql)

    # 若旧版本 users 表已存在但缺少 password_hash 等字段，补充列定义（兼容不支持 IF NOT EXISTS 的 MySQL 版本）
    try:
        rows = mysql_client.execute_query(
            "SHOW COLUMNS FROM users LIKE :col",
            {"col": "password_hash"},
        )
        has_col = bool(rows)
    except Exception as e:  # pragma: no cover - 仅调试
        from loguru import logger as _logger
        _logger.debug(f"check users.password_hash column failed: {e}")
        has_col = False

    if not has_col:
        mysql_client.execute_update(
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL AFTER email"
        )

    # 兼容旧表结构：将原有 password 列改为可为空，避免 NOT NULL 无默认值导致插入失败
    try:
        mysql_client.execute_update(
            "ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NULL DEFAULT NULL"
        )
    except Exception as e:  # pragma: no cover - 仅调试
        from loguru import logger as _logger
        _logger.debug(f"ensure users.password nullable: {e}")


def _ensure_knowledge_bases_table() -> None:
    """确保存在 knowledge_bases 表，用于持久化「我创建的」知识库列表。"""
    if not mysql_client:
        return
    create_sql = """
    CREATE TABLE IF NOT EXISTS knowledge_bases (
        kb_id VARCHAR(64) PRIMARY KEY COMMENT '知识库唯一标识',
        name VARCHAR(128) NOT NULL COMMENT '知识库名称',
        user_id VARCHAR(64) NOT NULL COMMENT '创建者 user_id',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档知识库列表';
    """
    try:
        mysql_client.execute_update(create_sql)
        try:
            mysql_client.execute_update(
                "CREATE INDEX idx_kb_user_id ON knowledge_bases (user_id)"
            )
        except Exception:
            pass  # 索引已存在时忽略
    except Exception as e:
        from loguru import logger as _logger
        _logger.warning(f"ensure knowledge_bases table failed: {e}")


def _hash_password(password: str) -> str:
    """使用 SHA256 做简单加密（示例项目，非生产级别）。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == (password_hash or "")


def _get_user_by_username(username: str):
    """根据用户名查询用户记录。"""
    if not mysql_client:
        return None
    _ensure_users_table()
    rows = mysql_client.execute_query(
        "SELECT user_id, username, email, password_hash FROM users WHERE username = :username",
        {"username": username},
    )
    return rows[0] if rows else None


# 定义任务状态枚举
class TaskStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 全局存储
uploaded_files = {}
"""
上传文件存储字典
格式: {file_id: {"filename": str, "path": str, "size": int, "uploaded_at": str, "content": str}}
"""

tasks = {}
"""
任务状态存储字典
格式: {task_id: {"status": str, "progress": int, "current_chunk": int, "total_chunks": int, "entities_created": int, "relations_created": int, "message": str, "current_processing": str, "file_id": str}}
"""

history_records = {}
"""
历史记录存储字典
格式: {record_id: {"id": str, "type": str, "file_id": str, "file_name": str, "task_id": str, "status": str, "message": str, "created_at": str, "processed_at": str}}
"""

history_counter = 1
"""历史记录ID计数器"""

# 知识库（多知识库）存储：kb_id -> { id, name, user_id, created_at }
knowledge_bases: Dict[str, Dict[str, Any]] = {}
DEFAULT_KB_ID = "default"
DEFAULT_KB_NAME = "我的知识库"

# 尝试注册 Hadoop 集成 API 路由
try:
    from backend.hadoop_api import router as hadoop_router
    app.include_router(hadoop_router)
    logger.info("Hadoop 集成 API 路由注册成功")
except Exception as e:
    logger.warning(f"Hadoop 集成 API 路由注册失败: {e},相关功能将不可用")

# 注册问答 API（/api/query），供 Chat 使用；后续可切换为 LangGraph Agent
try:
    from backend.query_router import router as query_router
    app.include_router(query_router)
    logger.info("问答 API 路由注册成功 (POST /api/query)")
except Exception as e:
    logger.warning(f"问答 API 路由注册失败: {e}, Chat 问答将不可用")

# 注册 Agent 问答 API（/api/agent/query），供 Chat 使用 LangGraph Agent
try:
    from backend.agent_router import router as agent_router
    app.include_router(agent_router)
    logger.info("Agent 问答 API 路由注册成功 (POST /api/agent/query)")
except Exception as e:
    logger.warning(f"Agent 问答 API 路由注册失败: {e}, Chat Agent 问答将不可用")


# =============== 数据模板下载（内联注册，确保与 /api/kb 同进程生效） ===============

_TEMPLATE_DISEASE_JSON = json.dumps({
    "diseases": [{"name": "疾病名称", "category": "疾病分类", "description": "疾病描述", "common_symptoms": ["症状1", "症状2"], "department": "就诊科室"}]
}, ensure_ascii=False, indent=2)
_TEMPLATE_SYMPTOM_CSV = "id,name,severity,description\nsymptom_001,症状名称,轻度/中度/重度,症状描述\n"
_TEMPLATE_MEDICINE_JSON = json.dumps({
    "drugs": [{"name": "药物名称", "type": "药物类型", "usage": "用法", "dosage": "剂量", "treats": ["可治疗的疾病"]}]
}, ensure_ascii=False, indent=2)
_TEMPLATE_RELATION_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<knowledge-graph>\n  <relation>\n    <source>实体ID或名称</source>\n    <target>实体ID或名称</target>\n    <type>关系类型(如: has_symptom, treated_by)</type>\n  </relation>\n</knowledge-graph>\n'

_TEMPLATE_MAP = {
    "disease": (_TEMPLATE_DISEASE_JSON.encode("utf-8"), "疾病数据模板.json", "application/json"),
    "symptom": (_TEMPLATE_SYMPTOM_CSV.encode("utf-8"), "症状数据模板.csv", "text/csv"),
    "medicine": (_TEMPLATE_MEDICINE_JSON.encode("utf-8"), "药物数据模板.json", "application/json"),
    "relation": (_TEMPLATE_RELATION_XML.encode("utf-8"), "关系数据模板.xml", "application/xml"),
}


@app.get("/api/templates/{template_type}", tags=["数据模板"])
async def download_template(template_type: str):
    """下载数据模板。支持: disease, symptom, medicine, relation。"""
    if template_type not in _TEMPLATE_MAP:
        raise HTTPException(status_code=404, detail=f"未知模板类型: {template_type}")
    content, filename, media_type = _TEMPLATE_MAP[template_type]
    # HTTP 头仅支持 latin-1，中文名用 RFC 5987 filename*=UTF-8'' 编码
    ascii_name = f"{template_type}_template.{'json' if template_type in ('disease', 'medicine') else 'csv' if template_type == 'symptom' else 'xml'}"
    value = quote(filename, safe="")
    content_disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{value}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disp},
    )


# =============== 认证相关请求模型与接口（注册/登录） ===============


class RegisterRequest(BaseModel):
    username: str = Field(..., description="用户名", min_length=3, max_length=64)
    email: Optional[str] = Field(None, description="邮箱")
    password: str = Field(..., description="密码", min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名", min_length=3, max_length=64)
    password: str = Field(..., description="密码", min_length=8, max_length=128)


@app.post("/api/auth/register", tags=["认证"])
async def register_user(body: RegisterRequest):
    """简单注册接口：写入 users 表，供登录使用。"""
    if not mysql_client:
        raise HTTPException(status_code=500, detail="注册功能依赖 MySQL，请先配置数据库")

    username = body.username.strip()
    email = (body.email or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    # 检查是否已存在
    if _get_user_by_username(username):
        raise HTTPException(status_code=400, detail="用户名已存在，请更换用户名")

    _ensure_users_table()
    user_id = str(uuid.uuid4())
    password_hash = _hash_password(body.password)

    mysql_client.execute_update(
        """
        INSERT INTO users (user_id, username, email, password_hash)
        VALUES (:user_id, :username, :email, :password_hash)
        """,
        {
            "user_id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
        },
    )

    return {
        "status": "success",
        "data": {
            "id": user_id,
            "username": username,
            "email": email,
        },
    }


@app.post("/api/auth/login", tags=["认证"])
async def login_user(body: LoginRequest):
    """用户名/密码登录，返回简单 token 与用户信息。"""
    if not mysql_client:
        raise HTTPException(status_code=500, detail="登录功能依赖 MySQL，请先配置数据库")

    username = body.username.strip()
    user = _get_user_by_username(username)
    if not user or not _verify_password(body.password, user.get("password_hash")):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 示例项目中 token 仅作为前端会话标记，不做服务端校验
    token = f"mock-token-{uuid.uuid4()}"

    return {
        "status": "success",
        "token": token,
        "user": {
            "id": user.get("user_id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "role": "user",
        },
    }


class BuildKGFromFileRequest(BaseModel):
    """从前端接收构建知识图谱请求体"""
    file_id: str = Field(..., description="已上传文件的ID")

# 文件上传API
@app.post("/api/upload", tags=["文件上传"])
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件
    """
    try:
        # 生成唯一文件ID，保留扩展名便于 PDF/TXT 识别
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename or "")[1] or ""
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
        content = b''
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 每次读取1MB
                if not chunk:
                    break
                content += chunk
                f.write(chunk)
        size = len(content)
        # 提取正文（PDF/TXT），供单文件构建与批量构建使用
        pdf_text = ""
        is_pdf = file_ext.lower() == ".pdf"
        is_txt = file_ext.lower() == ".txt"
        if is_pdf:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    pdf_text = "\n\n".join([p.extract_text() or "" for p in pdf.pages])
                logger.info(f"单文件上传已提取PDF文本: {file_id}, 长度: {len(pdf_text)}")
            except Exception as e:
                logger.warning(f"单文件上传PDF提取失败: {file_id}, {e}")
                pdf_text = f"ERROR: {e}"
        elif is_txt:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    pdf_text = f.read()
                logger.info(f"单文件上传已读取TXT文本: {file_id}, 长度: {len(pdf_text)}")
            except Exception as e:
                logger.warning(f"单文件上传TXT读取失败: {file_id}, {e}")
                pdf_text = f"ERROR: {e}"
        # 存储文件信息（含 pdf_text 供批量构建使用）
        uploaded_files[file_id] = {
            "filename": file.filename,
            "path": file_path,
            "size": size,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content,
            "pdf_text": pdf_text,
            "is_pdf": is_pdf,
        }
        
        logger.info(f"文件上传成功: {file.filename} (ID: {file_id})")
        
        # 保存上传记录到MySQL或内存
        if mysql_client:
            try:
                history_id = mysql_client.create_history_record(
                    file_id=file_id,
                    file_name=file.filename,
                    file_type="upload",
                    task_id=file_id
                )
                logger.info(f"上传记录已保存到MySQL: {history_id}")
            except Exception as e:
                logger.error(f"保存上传记录到MySQL失败: {str(e)}")
        else:
            # 使用内存存储保存记录
            global history_counter
            history_id = str(history_counter)
            history_counter += 1
            
            history_records[history_id] = {
                "id": history_id,
                "type": "upload",
                "file_id": file_id,
                "file_name": file.filename,
                "task_id": file_id,
                "status": "success",
                "message": "文件上传成功",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logger.info(f"上传记录已保存到内存: {history_id}")
        
        return {
            "status": "success",
            "file_id": file_id,
            "filename": file.filename,
            "message": "文件上传成功"
        }
        
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


# ---------- 文档知识库：正文提取与入库 ----------

def _extract_text_for_ingest(
    path: Optional[str],
    filename: str,
    content: Optional[str] = None,
    pdf_text: Optional[str] = None,
    is_pdf: Optional[bool] = None,
) -> Tuple[str, str]:
    """
    从文件路径或已有内容提取正文，供入库分块使用。
    Returns:
        (text, source_type)，source_type 为 "pdf" | "txt" | "json"
    """
    ext = (os.path.splitext(filename or "")[1] or "").lower()
    if ext == ".pdf":
        st = "pdf"
    elif ext == ".json":
        st = "json"
    else:
        st = "txt"

    if st == "pdf":
        if pdf_text and pdf_text.strip() and not pdf_text.strip().startswith("ERROR:"):
            return (pdf_text.strip(), "pdf")
        if path and os.path.isfile(path):
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    t = "\n\n".join([(p.extract_text() or "") for p in pdf.pages])
                return (t.strip(), "pdf")
            except Exception as e:
                logger.warning(f"pdfplumber 提取 PDF 失败 path={path}: {e}")
        return ("", "pdf")

    if st == "json":
        raw = None
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception as e:
                logger.warning(f"读取 JSON 文件失败 path={path}: {e}")
        if not raw and content:
            raw = content
        if not raw:
            return ("", "json")
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                text = data.get("text") or data.get("content") or data.get("body")
                if text is None:
                    text = json.dumps(data, ensure_ascii=False)
            elif isinstance(data, str):
                text = data
            else:
                text = json.dumps(data, ensure_ascii=False)
            return (str(text).strip(), "json")
        except Exception:
            return (raw.strip(), "json")
    # txt 及其他
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return (f.read().strip(), st)
        except Exception as e:
            logger.warning(f"读取文本文件失败 path={path}: {e}")
    if content:
        return (str(content).strip(), st)
    return ("", st)


_chroma_store = None


def _get_chroma_store():
    global _chroma_store
    if _chroma_store is None:
        from backend.chroma_store import ChromaStore
        _chroma_store = ChromaStore()
    return _chroma_store


def _ingest_from_file_info(
    doc_id: str,
    path: Optional[str],
    source_file: str,
    content: Optional[str],
    pdf_text: Optional[str],
    is_pdf: bool,
    user_id: Optional[str],
    kb_id: str = DEFAULT_KB_ID,
    strategy: str = "fixed",
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
) -> Tuple[int, str]:
    """
    从文件信息提取正文、分块并写入 Chroma。供 ingest（file_id / multipart）与 reindex 复用。
    kb_id 写入每条 chunk 的 metadata，用于多知识库过滤。
    Returns:
        (chunk_count, message)
    """
    from backend.doc_chunking import chunk_text, chunk_id

    text, source_type = _extract_text_for_ingest(
        path=path, filename=source_file, content=content, pdf_text=pdf_text, is_pdf=is_pdf
    )
    if not (text and text.strip()):
        return (0, "提取的正文为空，未写入向量库")

    chunks = chunk_text(
        text=text,
        doc_id=doc_id,
        source_file=source_file,
        source_type=source_type,
        user_id=user_id,
        strategy=strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        extra_meta={"kb_id": (kb_id or DEFAULT_KB_ID).strip() or DEFAULT_KB_ID},
    )
    if not chunks:
        return (0, "分块结果为空，未写入向量库")

    ids = [chunk_id(doc_id, m["chunk_index"]) for _, m in chunks]
    texts = [t for t, _ in chunks]
    metadatas = [m for _, m in chunks]
    store = _get_chroma_store()
    store.add_batch(ids=ids, texts=texts, metadatas=metadatas)
    return (len(chunks), f"已入库 {len(chunks)} 个块")


# ---------- 知识库（多知识库）CRUD ----------


@app.get("/api/kb/bases", tags=["文档知识库"])
async def list_kb_bases(request: Request):
    """
    列出当前用户的知识库。始终包含默认知识库（id=default, name=我的知识库），
    以及用户通过「创建」添加的其它知识库（优先从 MySQL 读取，无 MySQL 时用内存）。
    返回：{ status, data: { list: [ { id, name, created_at? } ] } }。
    """
    current_user_id = get_current_user_id(request)
    out = [{"id": DEFAULT_KB_ID, "name": DEFAULT_KB_NAME}]
    if mysql_client:
        try:
            _ensure_knowledge_bases_table()
            rows = mysql_client.list_kb_bases(current_user_id)
            for r in rows:
                out.append({"id": r["id"], "name": r.get("name", "未命名"), "created_at": r.get("created_at")})
        except Exception as e:
            logger.warning(f"list_kb_bases from MySQL failed: {e}, fallback to memory")
            for kb_id, info in knowledge_bases.items():
                if info.get("user_id") == current_user_id:
                    out.append({
                        "id": kb_id,
                        "name": info.get("name", "未命名"),
                        "created_at": info.get("created_at"),
                    })
    else:
        for kb_id, info in knowledge_bases.items():
            if info.get("user_id") == current_user_id:
                out.append({
                    "id": kb_id,
                    "name": info.get("name", "未命名"),
                    "created_at": info.get("created_at"),
                })
    return {"status": "success", "data": {"list": out}}


class CreateKbBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="知识库名称")


@app.post("/api/kb/bases", tags=["文档知识库"])
async def create_kb_base(request: Request, body: CreateKbBody):
    """
    创建新知识库。优先写入 MySQL，无 MySQL 时写内存。返回：{ status, data: { id, name } }。
    """
    current_user_id = get_current_user_id(request)
    name = (body.name or "").strip() or "未命名知识库"
    kb_id = str(uuid.uuid4())
    if mysql_client:
        try:
            _ensure_knowledge_bases_table()
            mysql_client.create_kb_base(kb_id, name, current_user_id)
        except Exception as e:
            logger.warning(f"create_kb_base to MySQL failed: {e}, fallback to memory")
            knowledge_bases[kb_id] = {
                "id": kb_id,
                "name": name,
                "user_id": current_user_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    else:
        knowledge_bases[kb_id] = {
            "id": kb_id,
            "name": name,
            "user_id": current_user_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return {"status": "success", "data": {"id": kb_id, "name": name}}


class RenameKbBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="新名称")


@app.patch("/api/kb/bases/{kb_id}", tags=["文档知识库"])
async def rename_kb_base(request: Request, kb_id: str, body: RenameKbBody):
    """
    重命名知识库。默认知识库（id=default）不可重命名。优先更新 MySQL，无 MySQL 时更新内存。
    返回：{ status, data: { id, name } }。
    """
    if kb_id == DEFAULT_KB_ID:
        raise HTTPException(status_code=400, detail="默认知识库不可重命名")
    current_user_id = get_current_user_id(request)
    name = (body.name or "").strip() or "未命名知识库"
    if mysql_client:
        try:
            _ensure_knowledge_bases_table()
            n = mysql_client.rename_kb_base(kb_id, name, current_user_id)
            if n == 0:
                raise HTTPException(status_code=404, detail="知识库不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"rename_kb_base in MySQL failed: {e}, fallback to memory")
            if kb_id not in knowledge_bases or knowledge_bases[kb_id].get("user_id") != current_user_id:
                raise HTTPException(status_code=404, detail="知识库不存在")
            knowledge_bases[kb_id]["name"] = name
    else:
        if kb_id not in knowledge_bases or knowledge_bases[kb_id].get("user_id") != current_user_id:
            raise HTTPException(status_code=404, detail="知识库不存在")
        knowledge_bases[kb_id]["name"] = name
    return {"status": "success", "data": {"id": kb_id, "name": name}}


@app.post("/api/kb/documents/ingest", tags=["文档知识库"])
async def ingest_document(
    request: Request,
    file: Optional[UploadFile] = File(None),
    file_id: Optional[str] = Form(None),
    kb_id: Optional[str] = Form(None, description="目标知识库 id，不传则入库到「我的知识库」default"),
    user_id: Optional[str] = Form(None, description="已忽略，7.1 改用服务端 get_current_user_id"),
    strategy: str = Form("fixed"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(100),
):
    """
    文档入库：分块后写入 Chroma 向量库。7.1 固定 user_id=当前用户，仅能入库到自己的知识库。

    - 方式一（multipart）：传 file；doc_id 为新 uuid。
    - 方式二（file_id）：传 file_id（来自 /api/upload 或 /api/hadoop/upload/batch）；doc_id=file_id。
    - kb_id：可选，目标知识库 id，不传或传 default 则入库到默认知识库。
    - 支持 PDF、TXT、JSON。
    - 返回：{ status, doc_id, chunk_count, source_file, message }。
    """
    current_user_id = get_current_user_id(request)
    target_kb_id = (kb_id or "").strip() or DEFAULT_KB_ID
    path = None
    is_temp = False
    try:
        if file is not None:
            # 多部件上传：保存到临时文件
            fn = file.filename or "unknown"
            ext = os.path.splitext(fn)[1].lower() or ".bin"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            path = tmp.name
            try:
                content_bytes = await file.read()
                tmp.write(content_bytes)
            finally:
                tmp.close()
            is_temp = True
            source_file = fn
            doc_id = str(uuid.uuid4())
            content = None
            pdf_text = None
            is_pdf = ext == ".pdf"
        elif file_id is not None and (file_id := (file_id or "").strip()):
            if file_id not in uploaded_files:
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
            info = uploaded_files[file_id]
            path = info.get("path")
            source_file = info.get("filename", "unknown")
            doc_id = file_id
            content = info.get("content")
            pdf_text = info.get("pdf_text")
            is_pdf = info.get("is_pdf")
            if is_pdf is None:
                is_pdf = (os.path.splitext(source_file or "")[1] or "").lower() == ".pdf"
        else:
            raise HTTPException(status_code=400, detail="请提供 file 或 file_id")

        chunk_count, message = _ingest_from_file_info(
            doc_id=doc_id,
            path=path,
            source_file=source_file,
            content=content,
            pdf_text=pdf_text,
            is_pdf=is_pdf,
            user_id=current_user_id,
            kb_id=target_kb_id,
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return {
            "status": "success",
            "doc_id": doc_id,
            "chunk_count": chunk_count,
            "source_file": source_file,
            "message": message,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文档入库失败")
        raise HTTPException(status_code=500, detail=f"文档入库失败: {str(e)}")
    finally:
        if is_temp and path and os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _build_kb_where(
    user_id: Optional[str],
    source_type: Optional[str],
    kb_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """构建 Chroma where：user_id、source_type、kb_id 过滤。kb_id 为 default 或不传时不按 kb_id 过滤（兼容旧数据）。"""
    conds: List[Dict[str, Any]] = []
    if user_id:
        conds.append({"user_id": user_id})
    if source_type:
        conds.append({"source_type": source_type})
    if kb_id and kb_id.strip() and kb_id != DEFAULT_KB_ID:
        conds.append({"kb_id": kb_id.strip()})
    if not conds:
        return None
    if len(conds) == 1:
        return conds[0]
    return {"$and": conds}


@app.get("/api/kb/documents/search", tags=["文档知识库"])
async def search_documents(
    request: Request,
    q: str = Query(..., min_length=1, description="查询文本"),
    k: int = Query(10, ge=1, le=100, description="返回条数"),
    source_type: Optional[str] = Query(None, description="按 source_type 过滤，如 pdf/txt/json"),
    kb_id: Optional[str] = Query(None, description="按知识库 id 过滤，不传或 default 表示默认知识库（含旧数据）"),
):
    """
    文档语义检索：7.1 仅检索当前用户知识库；支持 source_type、kb_id 过滤。
    返回：{ status, data: [ { id, text, metadata, distance } ] }，distance 为余弦距离，越小越相似。
    """
    try:
        current_user_id = get_current_user_id(request)
        where = _build_kb_where(current_user_id, source_type, kb_id)
        store = _get_chroma_store()
        hits = store.search(query_text=q.strip(), k=k, where=where)
        return {"status": "success", "data": hits}
    except Exception as e:
        logger.exception("文档检索失败")
        raise HTTPException(status_code=500, detail=f"文档检索失败: {str(e)}")


@app.get("/api/kb/documents/list", tags=["文档知识库"])
async def list_documents(
    request: Request,
    source_type: Optional[str] = Query(None, description="按 source_type 过滤"),
    kb_id: Optional[str] = Query(None, description="按知识库 id 过滤，不传或 default 表示默认知识库"),
    limit: int = Query(500, ge=1, le=2000, description="返回文档数上限"),
):
    """
    文档列表：7.1 仅列出当前用户知识库；从 chunk 聚合出按 doc_id 的文档摘要。
    每项：doc_id, source_file, source_type, user_id, chunk_count。
    """
    try:
        current_user_id = get_current_user_id(request)
        where = _build_kb_where(current_user_id, source_type, kb_id)
        store = _get_chroma_store()
        chunks = store.get_chunks(where=where, limit=50000)
        # 按 doc_id 聚合
        doc_map: Dict[str, Dict[str, Any]] = {}
        for c in chunks:
            meta = c.get("metadata") or {}
            did = meta.get("doc_id") or c.get("id", "").split(":")[0]
            if not did:
                continue
            if did not in doc_map:
                doc_map[did] = {
                    "doc_id": did,
                    "source_file": meta.get("source_file", ""),
                    "source_type": meta.get("source_type", ""),
                    "user_id": meta.get("user_id"),
                    "chunk_count": 0,
                }
            doc_map[did]["chunk_count"] = doc_map[did]["chunk_count"] + 1
        list_ = sorted(doc_map.values(), key=lambda x: (x["doc_id"],))[:limit]
        return {"status": "success", "data": {"list": list_, "total": len(doc_map)}}
    except Exception as e:
        logger.exception("文档列表失败")
        raise HTTPException(status_code=500, detail=f"文档列表失败: {str(e)}")


@app.delete("/api/kb/documents/{doc_id}", tags=["文档知识库"])
async def delete_document(request: Request, doc_id: str):
    """
    按 doc_id 删除文档：7.1 仅能删除当前用户自己的 chunk；按 doc_id+user_id 条件删除。
    返回：{ status, message, deleted_chunks }。
    """
    try:
        current_user_id = get_current_user_id(request)
        store = _get_chroma_store()
        where_del = {"$and": [{"doc_id": doc_id}, {"user_id": current_user_id}]}
        chunks = store.get_chunks(where=where_del, limit=100000)
        n = len(chunks)
        store.delete(where=where_del)
        return {"status": "success", "message": "已删除", "deleted_chunks": n}
    except Exception as e:
        logger.exception("删除文档失败")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


class ReindexRequest(BaseModel):
    """重索引请求：仅支持通过 file_id 入库的文档（doc_id 需仍存在于 uploaded_files）。"""
    doc_id: str = Field(..., description="文档 id，且须为 file_id 且仍在 uploaded_files 中")
    user_id: Optional[str] = Field(None, description="写入 metadata 的 user_id，可选")
    strategy: str = Field("fixed", description="分块策略")
    chunk_size: int = Field(1000, ge=100, le=8000)
    chunk_overlap: int = Field(100, ge=0, le=2000)


@app.post("/api/kb/documents/reindex", tags=["文档知识库"])
async def reindex_document(request: Request, body: ReindexRequest):
    """
    重索引：7.1 先校验 doc 归属当前用户，再按 doc_id 删除旧 chunk，从 uploaded_files 重新入库。
    仅当 doc_id 存在于 uploaded_files 时可用。入库 user_id=当前用户。
    返回：{ status, doc_id, chunk_count, source_file, message }。
    """
    doc_id = (body.doc_id or "").strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id 不能为空")
    if doc_id not in uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="仅支持对通过 file_id 入库的文档重索引，且该 file_id 仍存在于上传列表",
        )
    current_user_id = get_current_user_id(request)
    store = _get_chroma_store()
    # 7.1 校验归属：若已有 chunk 且其 user_id 非空且不等于当前用户，则拒绝
    existing = store.get_chunks(where={"doc_id": doc_id}, limit=1)
    for c in existing:
        uid = (c.get("metadata") or {}).get("user_id")
        if uid is not None and str(uid).strip() and str(uid) != current_user_id:
            raise HTTPException(status_code=403, detail="无权重索引该文档")
    try:
        info = uploaded_files[doc_id]
        path = info.get("path")
        source_file = info.get("filename", "unknown")
        content = info.get("content")
        pdf_text = info.get("pdf_text")
        is_pdf = info.get("is_pdf")
        if is_pdf is None:
            is_pdf = (os.path.splitext(source_file or "")[1] or "").lower() == ".pdf"

        store.delete(where={"doc_id": doc_id})

        # 重索引时沿用已有 chunk 的 kb_id（若有），否则用默认
        existing_kb_id = DEFAULT_KB_ID
        for c in existing:
            bid = (c.get("metadata") or {}).get("kb_id")
            if bid:
                existing_kb_id = bid
                break
        chunk_count, message = _ingest_from_file_info(
            doc_id=doc_id,
            path=path,
            source_file=source_file,
            content=content,
            pdf_text=pdf_text,
            is_pdf=is_pdf,
            user_id=current_user_id,
            kb_id=existing_kb_id,
            strategy=body.strategy,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
        )
        return {
            "status": "success",
            "doc_id": doc_id,
            "chunk_count": chunk_count,
            "source_file": source_file,
            "message": message,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("重索引失败")
        raise HTTPException(status_code=500, detail=f"重索引失败: {str(e)}")


# 从文件生成知识图谱API
@app.post("/api/kg/build", tags=["知识图谱构建"])
async def build_kg_from_file(req: Request, body: BuildKGFromFileRequest):
    """
    从上传的文件生成知识图谱（异步）：真实提取正文（含 PDF）+ kg.builder 构建图谱。
    """
    try:
        file_id = body.file_id
        current_user_id = get_current_user_id(req)

        # 检查文件是否存在
        if file_id not in uploaded_files:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 初始化任务信息
        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": "任务已创建，开始处理",
            "current_processing": "初始化",
            "file_id": file_id
        }

        # 启动后台线程处理任务（传入 user_id 用于 MySQL 图谱归属）
        thread = threading.Thread(target=build_kg_background, args=(task_id, file_id, current_user_id))
        thread.start()
        
        logger.info(f"知识图谱构建任务已启动: {task_id} (文件: {file_id})")
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": "知识图谱构建任务已启动"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动知识图谱构建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

# 后台知识图谱构建函数（真实：正文提取 + kg.builder + Neo4j + MySQL）
def build_kg_background(task_id: str, file_id: str, user_id: str = ""):
    """
    后台线程：从上传文件提取正文（含 PDF），调用 kg.builder 用 LLM 提取实体/关系并写入 Neo4j，再写 MySQL 记录。
    """
    try:
        if file_id not in uploaded_files:
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "文件不存在",
                "current_processing": "",
                "file_id": file_id
            }
            return

        file_info = uploaded_files[file_id]
        filename = file_info.get("filename", "")
        path = file_info.get("path")
        content = file_info.get("content")
        pdf_text = file_info.get("pdf_text")
        ext = (os.path.splitext(filename or "")[1] or "").lower()
        is_pdf = ext == ".pdf"

        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 5,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": "正在提取正文...",
            "current_processing": "提取正文",
            "file_id": file_id
        }

        # 1. 真实正文提取（与文档入库一致：PDF 用 pdfplumber，TXT/JSON 从 path 或 content 读）
        text, source_type = _extract_text_for_ingest(
            path=path,
            filename=filename,
            content=content,
            pdf_text=pdf_text,
            is_pdf=is_pdf,
        )
        text = (text or "").strip()
        if not text:
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "提取正文为空，无法构建图谱（请确认文件为可读 PDF/TXT/JSON）",
                "current_processing": "",
                "file_id": file_id
            }
            return

        tasks[task_id] = {
            "status": TaskStatus.PROCESSING,
            "progress": 15,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": "正文已提取，正在调用图谱构建...",
            "current_processing": "构建知识图谱",
            "file_id": file_id
        }

        # 2. 调用真实图谱构建器（LLM 提取实体/关系 + Neo4j）
        if not neo4j_client:
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": "Neo4j 未连接，无法构建知识图谱",
                "current_processing": "",
                "file_id": file_id
            }
            return

        try:
            from llm.client import LLMClient
            from kg.builder import KnowledgeGraphBuilder
        except Exception as e:
            logger.exception("导入 kg.builder 或 LLM 失败")
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": f"依赖加载失败: {str(e)}",
                "current_processing": "",
                "file_id": file_id
            }
            return

        try:
            llm_client = LLMClient()
            builder = KnowledgeGraphBuilder(neo4j_client=neo4j_client, llm_client=llm_client)
            result = builder.process_text(text)
        except Exception as e:
            logger.exception("知识图谱构建执行失败")
            tasks[task_id] = {
                "status": TaskStatus.FAILED,
                "progress": 0,
                "current_chunk": 0,
                "total_chunks": 0,
                "entities_created": 0,
                "relations_created": 0,
                "message": f"构建失败: {str(e)}",
                "current_processing": "",
                "file_id": file_id
            }
            return

        entities_count = result.get("entities_created", 0)
        relations_count = result.get("relations_created", 0)
        paragraphs_processed = result.get("paragraphs_processed", 0)

        tasks[task_id] = {
            "status": TaskStatus.COMPLETED,
            "progress": 100,
            "current_chunk": paragraphs_processed,
            "total_chunks": paragraphs_processed,
            "entities_created": entities_count,
            "relations_created": relations_count,
            "message": f"知识图谱生成成功，共 {entities_count} 个实体、{relations_count} 条关系",
            "current_processing": "完成",
            "file_id": file_id
        }

        # 3. 将知识图谱记录存储到 MySQL（含节点与关系数据，供前端展示边）
        if mysql_client:
            try:
                graph_id = mysql_client.create_graph(
                    graph_name=filename,
                    description=f"从文件 {filename} 生成的知识图谱",
                    data_source=file_id,
                    file_path=file_id,
                    user_id=user_id or "default_user"
                )
                mysql_client.update_graph_status(
                    graph_id=graph_id,
                    status="completed",
                    entity_count=entities_count,
                    relation_count=relations_count
                )
                # 写入 graph_data（nodes + relations），前端 /api/graph/data 据此返回 nodes/edges
                entities = result.get("entities", [])
                relations_raw = result.get("relations", [])
                nodes_for_db = []
                seen_n = set()
                for e in entities:
                    name = (e.get("name") or "").strip()
                    if not name or name in seen_n:
                        continue
                    seen_n.add(name)
                    nodes_for_db.append({
                        "id": name,
                        "name": name,
                        "type": (e.get("type") or "entity").strip(),
                        "category": (e.get("type") or "entity").strip().lower(),
                        "description": (e.get("description") or "").strip(),
                    })
                relations_for_db = []
                seen_r = set()
                for r in relations_raw:
                    sub = (r.get("subject") or "").strip()
                    pred = (r.get("predicate") or "").strip()
                    obj = (r.get("object") or "").strip()
                    if not sub or not pred or not obj:
                        continue
                    rk = (sub, pred, obj)
                    if rk in seen_r:
                        continue
                    seen_r.add(rk)
                    relations_for_db.append({
                        "id": f"{sub}_{pred}_{obj}",
                        "source": sub,
                        "target": obj,
                        "relation": pred,
                    })
                mysql_client.update_graph_data(
                    graph_id,
                    {"nodes": nodes_for_db, "relations": relations_for_db}
                )
                logger.info(f"知识图谱记录已存储到 MySQL: {graph_id}, nodes={len(nodes_for_db)}, relations={len(relations_for_db)}")
            except Exception as e:
                logger.error(f"存储知识图谱记录到 MySQL 失败: {str(e)}")

    except Exception as e:
        logger.exception("知识图谱构建异常")
        tasks[task_id] = {
            "status": TaskStatus.FAILED,
            "progress": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "message": f"知识图谱构建失败: {str(e)}",
            "current_processing": "",
            "file_id": file_id
        }


class ChatHistoryCreate(BaseModel):
    """用于保存聊天历史的请求模型"""
    id: int
    type: str
    title: str
    content: Dict[str, Any]
    status: str
    entities: List[Any] = []
    createTime: str
    updateTime: str


@app.get("/api/history/list", tags=["历史记录"])
async def get_history_list(
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    获取历史记录列表，最多返回 limit 条（默认 1000）。

    当存在 MySQL 客户端时，仅从数据库读取格式化后的历史记录；
    如果没有 MySQL，则退回到仅使用内存中的 history_records。
    """
    try:
        history_list: List[Dict[str, Any]] = []

        # 1. 如果有 MySQL，优先只用数据库中的历史记录（已按前端结构转换）
        if mysql_client:
            history_list = mysql_client.get_histories(limit=limit, offset=offset)
        else:
            # 2. 否则仅使用内存中的历史记录
            history_list = list(history_records.values())

        # 3. 统一按类型、状态过滤
        if type:
            history_list = [record for record in history_list if record.get("type") == type]

        if status:
            history_list = [record for record in history_list if record.get("status") == status]

        # 4. 内存模式：排序后截取 limit/offset；MySQL 已在 get_histories 内分页
        if not mysql_client:
            history_list.sort(key=lambda r: r.get("created_at") or r.get("createTime") or "", reverse=True)
            history_list = history_list[offset : offset + limit]

        return {
            "status": "success",
            "data": {
                "list": history_list,
                "total": len(history_list)
            }
        }
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")

# 获取历史记录统计API
@app.get("/api/history/stats", tags=["历史记录"])
async def get_history_stats():
    """
    获取历史记录统计信息
    """
    try:
        if mysql_client:
            stats = mysql_client.get_history_stats()
            return {
                "status": "success",
                "data": stats
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except Exception as e:
        logger.error(f"获取历史记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史记录统计失败: {str(e)}")


@app.post("/api/history/save", tags=["历史记录"])
async def save_history(record: ChatHistoryCreate):
    """
    保存聊天/图谱/上传等历史记录
    当前实现：
    - 如果配置了 MySQL，则尝试写入 MySQL（需要 mysql_client 支持对应方法）；
    - 否则先写入内存 history_records，保证前端不报错。
    """
    try:
        global history_counter

        # 转成通用 dict
        record_dict = record.model_dump()

        # 内存中的 ID 统一用字符串，方便前端展示
        history_id = str(record_dict.get("id") or history_counter)

        # 映射一些字段名以便后续扩展
        stored = {
            "id": history_id,
            "type": record_dict.get("type", "chat"),
            "title": record_dict.get("title", ""),
            "content": record_dict.get("content", {}),
            "status": record_dict.get("status", "completed"),
            "entities": record_dict.get("entities", []),
            "created_at": record_dict.get("createTime"),
            "updated_at": record_dict.get("updateTime"),
        }

        # 优先尝试保存到 MySQL（使用已有的 save_history_record 方法）
        if mysql_client and hasattr(mysql_client, "save_history_record"):
            try:
                mysql_id = mysql_client.save_history_record(stored)
                # 如果 MySQL 返回了新的 ID，则覆盖本地 ID
                if mysql_id:
                    stored["id"] = str(mysql_id)
                # 已成功写入数据库时，不再写入内存，避免重复与 ID 冲突
            except Exception as e:
                logger.error(f"保存聊天历史到 MySQL 失败: {e}")
                # 回退到内存存储
                history_records[history_id] = stored
                history_counter += 1
        else:
            # 没有 MySQL 时仅使用内存存储
            history_records[history_id] = stored
            history_counter += 1

        return {
            "status": "success",
            "data": stored
        }

    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存历史记录失败: {str(e)}")


@app.put("/api/history/{history_id}/status", tags=["历史记录"])
async def update_history_status(history_id: str, body: Optional[dict] = Body(None)):
    """更新历史记录状态（前端上传进度/完成/失败时调用）"""
    if not history_id or history_id == "undefined":
        raise HTTPException(status_code=400, detail="历史记录 ID 无效")
    try:
        status = (body or {}).get("status") if isinstance(body, dict) else None
        if not status:
            raise HTTPException(status_code=400, detail="缺少 status")
        if mysql_client and hasattr(mysql_client, "update_history_record_status"):
            mysql_client.update_history_record_status(history_id, status)
        elif history_id in history_records:
            history_records[history_id]["status"] = status
        return {"status": "success", "data": {"id": history_id, "status": status}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新历史记录状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 注意：必须先注册字面路径 /clear，再注册 /{history_id}，否则 clear 会被当作 history_id 匹配
@app.delete("/api/history/clear", tags=["历史记录"])
async def clear_history_all(request: Request):
    """清空历史记录；可按当前用户清空或清空全部（由前端传参或后端策略决定，此处清空全部）"""
    try:
        if not mysql_client or not hasattr(mysql_client, "clear_history"):
            raise HTTPException(status_code=501, detail="清空历史功能未就绪")
        # 可选：仅清空当前用户 current_user_id = get_current_user_id(request); mysql_client.clear_history(user_id=current_user_id)
        n = mysql_client.clear_history(user_id=None)
        return {"status": "success", "message": f"已清空 {n} 条历史", "deleted": n}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/history/{history_id}", tags=["历史记录"])
async def delete_history_one(history_id: str):
    """删除单条历史记录"""
    if not history_id or history_id == "undefined":
        raise HTTPException(status_code=400, detail="历史记录 ID 无效")
    try:
        if not mysql_client or not hasattr(mysql_client, "delete_history"):
            raise HTTPException(status_code=501, detail="历史删除功能未就绪")
        n = mysql_client.delete_history(history_id)
        if n == 0:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        return {"status": "success", "message": "已删除", "deleted": 1}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BatchDeleteHistoryBody(BaseModel):
    """批量删除历史记录请求体，兼容 ids / history_ids"""
    history_ids: Optional[List[str]] = Field(None, description="历史记录 ID 列表")
    ids: Optional[List[str]] = Field(None, description="历史记录 ID 列表（兼容前端）")


@app.post("/api/history/batch-delete", tags=["历史记录"])
async def batch_delete_history(body: BatchDeleteHistoryBody):
    """批量删除历史记录"""
    ids = (body.history_ids or body.ids or [])
    if not ids:
        raise HTTPException(status_code=400, detail="请提供 history_ids 或 ids")
    try:
        if not mysql_client or not hasattr(mysql_client, "delete_history_batch"):
            raise HTTPException(status_code=501, detail="批量删除功能未就绪")
        n = mysql_client.delete_history_batch(ids)
        return {"status": "success", "message": f"已删除 {n} 条", "deleted": n}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 获取知识图谱列表API
@app.get("/api/kg/list", tags=["知识图谱"])
async def get_kg_list():
    """
    获取已生成的知识图谱列表
    """
    try:
        if mysql_client:
            # 查询所有知识图谱记录
            kg_records = mysql_client.get_graphs()
            
            # 转换为前端期望的格式
            formatted_records = []
            for record in kg_records:
                formatted_records.append({
                    "id": record.get('graph_id', ''),
                    "name": record.get('graph_name', ''),
                    "description": record.get('description', ''),
                    "file_path": record.get('file_path', ''),
                    "status": record.get('status', ''),
                    "entities_count": record.get('entity_count', 0),
                    "relations_count": record.get('relation_count', 0),
                    "created_at": record.get('created_at', '')
                })
            
            return {
                "status": "success",
                "data": {
                    "list": formatted_records,
                    "total": len(formatted_records)
                }
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except Exception as e:
        logger.error(f"获取知识图谱列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱列表失败: {str(e)}")


# 图谱列表（兼容前端 graphApi.getGraphList：GET /api/graph/list）
# 返回 graph_id, graph_name, entity_count, relation_count，便于 GraphView 图谱切换；按当前用户过滤，切换图谱时只显示该图谱数据
@app.get("/api/graph/list", tags=["知识图谱"])
async def get_graph_list(request: Request):
    """获取图谱列表，格式与 GraphView 的 graphList 一致；仅返回当前用户的图谱"""
    try:
        if not mysql_client:
            return {"status": "success", "data": {"list": [], "total": 0}}
        current_user_id = get_current_user_id(request)
        kg_records = mysql_client.get_graphs(user_id=current_user_id)
        list_ = []
        for r in kg_records:
            gid = r.get("graph_id", "") or r.get("id", "")
            list_.append({
                "graph_id": gid,
                "graph_name": r.get("graph_name", "") or r.get("name", ""),
                "entity_count": r.get("entity_count", 0) or r.get("entities_count", 0),
                "relation_count": r.get("relation_count", 0) or r.get("relations_count", 0),
                "id": gid,
                "name": r.get("graph_name", "") or r.get("name", ""),
                "description": r.get("description", ""),
                "status": r.get("status", ""),
                "created_at": r.get("created_at", ""),
            })
        return {"status": "success", "data": {"list": list_, "total": len(list_)}}
    except Exception as e:
        logger.error(f"获取图谱列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/graph/clear", tags=["知识图谱"])
async def clear_graph_all(request: Request):
    """清空所有图谱：Neo4j 全部删除 + MySQL knowledge_graphs 清空"""
    try:
        if neo4j_client:
            neo4j_client.delete_all()
        if mysql_client and hasattr(mysql_client, "clear_all_graphs"):
            n = mysql_client.clear_all_graphs()
        else:
            n = 0
        return {"status": "success", "message": "已清空图谱", "deleted_graphs": n}
    except Exception as e:
        logger.error(f"清空图谱失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/graph/{graph_id}", tags=["知识图谱"])
async def delete_graph_one(request: Request, graph_id: str):
    """按 graph_id 删除单个图谱（仅 MySQL；Neo4j 当前未按图隔离则仅删元数据）"""
    if not graph_id or graph_id == "undefined":
        raise HTTPException(status_code=400, detail="图谱 ID 无效")
    try:
        if not mysql_client:
            raise HTTPException(status_code=501, detail="图谱删除功能未就绪")
        current_user_id = get_current_user_id(request)
        rec = mysql_client.get_graph_by_id(graph_id)
        if not rec:
            rec = mysql_client.get_graph_by_data_source(graph_id)
        if not rec:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        if rec.get("user_id") and rec.get("user_id") != current_user_id:
            raise HTTPException(status_code=403, detail="无权删除该图谱")
        mysql_client.delete_graph(graph_id)
        return {"status": "success", "message": "已删除", "graph_id": graph_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除图谱失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 获取知识图谱详情API
@app.get("/api/kg/{graph_id}", tags=["知识图谱"])
async def get_kg_detail(graph_id: str):
    """
    获取知识图谱详情
    """
    try:
        if mysql_client:
            kg_record = mysql_client.get_graph_by_id(graph_id)
            if not kg_record:
                raise HTTPException(status_code=404, detail="知识图谱不存在")
            
            # 转换为前端期望的格式
            formatted_record = {
                "id": kg_record.get('graph_id', ''),
                "name": kg_record.get('graph_name', ''),
                "description": kg_record.get('description', ''),
                "file_path": kg_record.get('file_path', ''),
                "status": kg_record.get('status', ''),
                "entities_count": kg_record.get('entity_count', 0),
                "relations_count": kg_record.get('relation_count', 0),
                "created_at": kg_record.get('created_at', '')
            }
            
            return {
                "status": "success",
                "data": formatted_record
            }
        else:
            return {
                "status": "error",
                "message": "MySQL客户端未初始化"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱详情失败: {str(e)}")

# 获取知识图谱可视化数据API
@app.get("/api/kg/{graph_id}/visualize", tags=["知识图谱"])
async def get_kg_visualize_data(graph_id: str):
    """
    获取知识图谱可视化数据（节点和关系）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "nodes": [],
                    "relations": [],
                    "total_nodes": 0,
                    "total_relations": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取节点和关系数据
        nodes = graph_data.get("nodes", [])
        relations = graph_data.get("relations", [])
        
        return {
            "status": "success",
            "data": {
                "nodes": nodes,
                "relations": relations,
                "total_nodes": len(nodes),
                "total_relations": len(relations)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱可视化数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱可视化数据失败: {str(e)}")

# 获取知识图谱节点列表API
@app.get("/api/kg/{graph_id}/nodes", tags=["知识图谱"])
async def get_kg_nodes(graph_id: str):
    """
    获取知识图谱节点列表
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取节点数据
        nodes = graph_data.get("nodes", [])
        
        return {
            "status": "success",
            "data": {
                "list": nodes,
                "total": len(nodes)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱节点列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱节点列表失败: {str(e)}")

# 获取知识图谱关系列表API
@app.get("/api/kg/{graph_id}/relations", tags=["知识图谱"])
async def get_kg_relations(graph_id: str):
    """
    获取知识图谱关系列表
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 从数据库获取知识图谱数据
        kg_record = mysql_client.get_graph_by_id(graph_id)
        if not kg_record:
            raise HTTPException(status_code=404, detail="知识图谱不存在")
        
        # 解析graph_data字段
        graph_data = kg_record.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)
        
        # 获取关系数据
        relations = graph_data.get("relations", [])
        
        return {
            "status": "success",
            "data": {
                "list": relations,
                "total": len(relations)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱关系列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识图谱关系列表失败: {str(e)}")

# 为前端添加的兼容API - 获取图谱数据
# 返回 nodes、edges（=relations）在顶层，便于 GraphView 使用 response.data.nodes / response.data.edges；按当前用户过滤，传 graph_id 时只返回该图谱
@app.get("/api/graph/data", tags=["知识图谱"])
async def get_graph_data(
    request: Request,
    graph_id: Optional[str] = Query(None, description="只返回该图谱；不传则合并当前用户全部图谱"),
    limit: Optional[int] = Query(500, ge=1, le=2000, description="节点数量上限"),
):
    """
    获取图谱数据。顶层返回 nodes、edges，与 ECharts graph 的 data/links 对齐。仅返回当前用户的图谱。
    """
    try:
        if not mysql_client:
            return {"status": "success", "nodes": [], "edges": [], "total_nodes": 0, "total_relations": 0}

        def _parse(g):
            raw = g.get("graph_data")
            if raw is None:
                return [], []
            d = raw if isinstance(raw, dict) else {}
            if isinstance(raw, str):
                try:
                    d = json.loads(raw)
                except Exception as e:
                    logger.warning(f"graph_data JSON 解析失败: {e}")
                    d = {}
            if not isinstance(d, dict):
                d = {}
            nodes = d.get("nodes", [])
            # 兼容存储键名 edges / relations（mysql 中统一存为 edges）
            relations = d.get("edges") or d.get("relations") or []
            if not isinstance(relations, list):
                relations = []
            rec_relations = (g.get("relation_count") or g.get("relations_count") or 0) or 0
            if rec_relations > 0 and len(relations) == 0:
                logger.warning(
                    f"图谱 graph_data 中边为空但 relation_count={rec_relations}, graph_id={g.get('graph_id')}, keys={list(d.keys())}"
                )
            return nodes, relations

        current_user_id = get_current_user_id(request)
        if graph_id:
            rec = mysql_client.get_graph_by_id(graph_id)
            if not rec:
                rec = mysql_client.get_graph_by_data_source(graph_id)
            if not rec:
                raise HTTPException(status_code=404, detail="知识图谱不存在")
            if rec.get("user_id") != current_user_id:
                raise HTTPException(status_code=404, detail="知识图谱不存在或无权访问")
            graphs = [rec]
        else:
            graphs = mysql_client.get_graphs(user_id=current_user_id)

        all_nodes = []
        all_relations = []
        seen_n = set()
        seen_r = set()

        for g in graphs:
            nodes, relations = _parse(g)
            for n in nodes:
                nid = n.get("id") or n.get("name")
                if nid and nid not in seen_n:
                    seen_n.add(nid)
                    raw = (n.get("type") or n.get("label") or n.get("category") or "entity")
                    n = dict(n)
                    n["id"] = n.get("id") or n.get("name") or nid
                    n["category"] = raw.lower() if isinstance(raw, str) else "entity"
                    all_nodes.append(n)
                    if len(all_nodes) >= limit:
                        break
            # 当前图谱的边必须在达到 limit 后也加入，否则会出现有节点无边
            for r in relations:
                src = r.get("source") or r.get("subject")
                tgt = r.get("target") or r.get("object")
                rel = r.get("relation") or r.get("predicate") or r.get("type") or ""
                if not src or not tgt:
                    continue
                rid = r.get("id") or f"{src}_{rel}_{tgt}"
                if rid in seen_r:
                    continue
                seen_r.add(rid)
                all_relations.append({
                    "id": rid,
                    "source": str(src).strip(),
                    "target": str(tgt).strip(),
                    "relation": rel,
                    "value": rel,
                })
            if len(all_nodes) >= limit:
                break

        # 顶层 nodes、edges 供 GraphView（response.data.nodes / response.data.edges）
        # data 保留旧形状，兼容既用 data.nodes / data.relations 的调用
        return {
            "status": "success",
            "nodes": all_nodes,
            "edges": all_relations,
            "total_nodes": len(all_nodes),
            "total_relations": len(all_relations),
            "data": {"nodes": all_nodes, "relations": all_relations, "total_nodes": len(all_nodes), "total_relations": len(all_relations)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 为前端添加的兼容API - 获取实体详情
@app.get("/api/graph/entity/{entity_id}", tags=["知识图谱"])
async def get_entity_detail(entity_id: str):
    """
    获取实体详情（兼容前端API）
    """
    try:
        if not mysql_client:
            raise HTTPException(status_code=404, detail="实体不存在")
        
        entity = None
        entity_relations = []
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找指定ID的实体和相关关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            relations = graph_data.get("relations", [])
            
            # 查找实体
            for node in nodes:
                if node["id"] == entity_id:
                    entity = node
                    break
            
            # 查找与实体相关的关系
            for relation in relations:
                if relation["source"] == entity_id or relation["target"] == entity_id:
                    # 构建关系数据
                    if relation["source"] == entity_id:
                        relation_info = {
                            "id": relation["id"],
                            "target": relation["target"],
                            "label": relation["label"]
                        }
                    else:
                        relation_info = {
                            "id": relation["id"],
                            "source": relation["source"],
                            "label": relation["label"]
                        }
                    entity_relations.append(relation_info)
            
            # 如果找到了实体，提前退出循环
            if entity:
                break
        
        # 如果实体不存在
        if not entity:
            raise HTTPException(status_code=404, detail="实体不存在")
        
        # 构建完整的实体详情
        entity_detail = {
            "id": entity["id"],
            "label": entity["label"],
            "type": entity["type"],
            "properties": entity.get("properties", {}),
            "relations": entity_relations
        }
        
        return {
            "status": "success",
            "data": entity_detail
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实体详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取实体详情失败: {str(e)}")

# 为前端添加的兼容API - 获取关系详情
@app.get("/api/graph/relation/{relation_id}", tags=["知识图谱"])
async def get_relation_detail(relation_id: str):
    """
    获取关系详情（兼容前端API）
    """
    try:
        if not mysql_client:
            raise HTTPException(status_code=404, detail="关系不存在")
        
        relation = None
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找指定ID的关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            relations = graph_data.get("relations", [])
            
            # 查找关系
            for rel in relations:
                if rel["id"] == relation_id:
                    relation = rel
                    break
            
            # 如果找到了关系，提前退出循环
            if relation:
                break
        
        # 如果关系不存在
        if not relation:
            raise HTTPException(status_code=404, detail="关系不存在")
        
        return {
            "status": "success",
            "data": relation
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关系详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取关系详情失败: {str(e)}")

def _search_graph_entities(keyword: str = "", node_type: str = "") -> List[Dict[str, Any]]:
    """
    通用的实体搜索逻辑，供多个接口复用
    优先从 Neo4j 搜索（与图谱显示数据源一致），如果没有 Neo4j 则回退到 MySQL
    """
    logger.info(f"[search_entities] 开始搜索实体, keyword='{keyword}', type='{node_type}'")

    # 优先使用 Neo4j 搜索（与前端图谱显示的数据源一致）
    if neo4j_client:
        try:
            # 使用 Neo4j 的 search_entities 方法
            neo4j_results = neo4j_client.search_entities(
                keyword=keyword,
                node_type=node_type if node_type else None,
                limit=100
            )
            
            # 转换为前端期望的格式
            formatted_nodes = []
            for entity in neo4j_results:
                # Neo4j 返回的格式: {id, type, name, properties}
                # 转换为前端期望的格式: {id, name, type, category, ...}
                node = {
                    'id': entity.get('id', ''),
                    'name': entity.get('name', ''),
                    'type': entity.get('type', ''),
                    'category': entity.get('type', ''),  # type 和 category 都设为节点类型
                    'properties': entity.get('properties', {}),
                    'summary': entity.get('properties', {}).get('description', '') or entity.get('properties', {}).get('summary', ''),
                }
                formatted_nodes.append(node)
            
            logger.info(f"[search_entities] Neo4j搜索完成, 命中节点数={len(formatted_nodes)}")
            return formatted_nodes
            
        except Exception as e:
            logger.warning(f"Neo4j搜索失败: {e}，回退到MySQL搜索")
            # 继续执行下面的 MySQL 搜索逻辑

    # 回退到 MySQL 搜索（如果没有 Neo4j 或 Neo4j 搜索失败）
    if not mysql_client:
        logger.warning("[search_entities] MySQL客户端未初始化，返回空结果")
        return []

    all_nodes: List[Dict[str, Any]] = []
    node_ids: set = set()

    # 从数据库获取所有知识图谱数据
    graphs = mysql_client.get_graphs()

    # 查找匹配的实体
    for gi, graph in enumerate(graphs):
        graph_data = graph.get("graph_data", {})
        if isinstance(graph_data, str):
            import json
            graph_data = json.loads(graph_data)

        nodes = graph_data.get("nodes", [])

        for ni, node in enumerate(nodes):
            if node["id"] in node_ids:
                continue

            # 将整个节点序列化成字符串，做一个"兜底"的模糊匹配
            try:
                import json as _json
                node_text = _json.dumps(node, ensure_ascii=False)
            except Exception:
                node_text = str(node)

            # 关键字匹配：节点整体文本中包含关键字即可
            match_keyword = (not keyword) or (keyword.lower() in node_text.lower())

            # 类型匹配
            match_type = not node_type or node_type == node.get("type")

            if match_keyword and match_type:
                node_ids.add(node["id"])
                all_nodes.append(node)

    logger.info(
        f"[search_entities] MySQL搜索完成, 图谱数={len(graphs)}, 命中节点数={len(all_nodes)}"
    )

    return all_nodes


# 为前端添加的兼容API - 原有图谱实体搜索接口
@app.get("/api/graph/entities/search", tags=["知识图谱"])
async def search_entities_legacy(keyword: Optional[str] = None, type: Optional[str] = None):
    """
    搜索图谱实体（兼容老的 /api/graph/entities/search，用于内部或调试）
    """
    try:
        keyword_str = keyword or ""
        type_str = type or ""
        all_nodes = _search_graph_entities(keyword_str, type_str)
        return {
            "status": "success",
            "data": {
                "list": all_nodes,
                "total": len(all_nodes),
            },
        }
    except Exception as e:
        logger.error(f"搜索实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索实体失败: {str(e)}")


# 新的实体搜索接口 - 提供给前端 SearchView.vue 使用
@app.get("/api/search/entities", tags=["搜索"])
async def search_entities(keyword: Optional[str] = None, type: Optional[str] = None, limit: int = 50):
    """
    实体搜索接口：
    - GET /api/search/entities?keyword=糖尿病&type=disease&limit=10
    - 返回 data: [entities...]，方便前端直接使用
    """
    try:
        keyword_str = keyword or ""
        type_str = type or ""
        all_nodes = _search_graph_entities(keyword_str, type_str)

        # 应用 limit
        if limit and limit > 0:
            all_nodes = all_nodes[:limit]

        return {
            "status": "success",
            "data": all_nodes,
        }
    except Exception as e:
        logger.error(f"实体搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"实体搜索失败: {str(e)}")

# 为前端添加的兼容API - 搜索图谱关系
@app.get("/api/graph/relations/search", tags=["知识图谱"])
async def search_relations(params: Optional[Dict[str, Any]] = None):
    """
    搜索图谱关系（兼容前端API）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "list": [],
                    "total": 0
                }
            }
        
        # 获取搜索参数
        keyword = params.get("keyword", "") if params else ""
        relation_label = params.get("label", "") if params else ""
        
        all_relations = []
        relation_ids = set()
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找匹配的关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            relations = graph_data.get("relations", [])
            
            for relation in relations:
                if relation["id"] not in relation_ids:
                    # 检查是否匹配搜索条件
                    match_keyword = not keyword or \
                                   keyword.lower() in relation["label"].lower() or \
                                   any(keyword.lower() in str(value).lower() for value in relation.get("properties", {}).values())
                    match_label = not relation_label or relation_label == relation["label"]
                    
                    if match_keyword and match_label:
                        relation_ids.add(relation["id"])
                        all_relations.append(relation)
        
        return {
            "status": "success",
            "data": {
                "list": all_relations,
                "total": len(all_relations)
            }
        }
    except Exception as e:
        logger.error(f"搜索关系失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索关系失败: {str(e)}")

# 为前端添加的兼容API - 扩展实体
@app.get("/api/graph/entity/{entity_id}/expand", tags=["知识图谱"])
async def expand_entity(entity_id: str, params: Optional[Dict[str, Any]] = None):
    """
    扩展实体（兼容前端API）
    """
    try:
        if not mysql_client:
            return {
                "status": "success",
                "data": {
                    "nodes": [],
                    "relations": []
                }
            }
        
        expanded_nodes = []
        expanded_relations = []
        node_ids = set()
        relation_ids = set()
        
        # 从数据库获取所有知识图谱数据
        graphs = mysql_client.get_graphs()
        
        # 查找与指定实体相关的节点和关系
        for graph in graphs:
            graph_data = graph.get("graph_data", {})
            if isinstance(graph_data, str):
                import json
                graph_data = json.loads(graph_data)
            
            nodes = graph_data.get("nodes", [])
            relations = graph_data.get("relations", [])
            
            # 查找与实体相关的关系
            for relation in relations:
                if relation["source"] == entity_id or relation["target"] == entity_id:
                    # 添加关系（去重）
                    if relation["id"] not in relation_ids:
                        relation_ids.add(relation["id"])
                        expanded_relations.append(relation)
                    
                    # 添加相关节点（去重）
                    if relation["source"] == entity_id:
                        # 添加目标节点
                        for node in nodes:
                            if node["id"] == relation["target"] and node["id"] not in node_ids:
                                node_ids.add(node["id"])
                                expanded_nodes.append(node)
                                break
                    else:
                        # 添加源节点
                        for node in nodes:
                            if node["id"] == relation["source"] and node["id"] not in node_ids:
                                node_ids.add(node["id"])
                                expanded_nodes.append(node)
                                break
        
        return {
            "status": "success",
            "data": {
                "nodes": expanded_nodes,
                "relations": expanded_relations
            }
        }
    except Exception as e:
        logger.error(f"扩展实体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"扩展实体失败: {str(e)}")

# 获取单个文件构建任务进度API
@app.get("/api/kg/build/progress/{task_id}", tags=["知识图谱构建"])
async def get_kg_build_progress(task_id: str):
    """
    获取单个文件知识图谱构建任务进度
    """
    try:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        task = tasks[task_id]
        return {
            "status": "success",
            "task_id": task_id,
            "progress": task.get("progress", 0),
            "status": task.get("status", "unknown"),
            "current_chunk": task.get("current_chunk", 0),
            "total_chunks": task.get("total_chunks", 0),
            "entities_created": task.get("entities_created", 0),
            "relations_created": task.get("relations_created", 0),
            "message": task.get("message", ""),
            "current_processing": task.get("current_processing", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务进度失败: {str(e)}")

# 搜索历史记录API
@app.get("/api/history/search", tags=["历史记录"])
async def search_history(keyword: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None):
    """
    搜索历史记录
    """
    try:
        if mysql_client:
            history_list = mysql_client.search_history_records(keyword, type, status)
        else:
            # 使用内存存储的历史记录进行搜索
            history_list = list(history_records.values())
            
            # 根据关键字过滤
            if keyword:
                keyword = keyword.lower()
                history_list = [
                    record for record in history_list 
                    if keyword in str(record.get('file_name', '')).lower() or 
                       keyword in str(record.get('message', '')).lower()
                ]
            
            # 根据类型过滤
            if type:
                history_list = [record for record in history_list if record.get('type') == type]
            
            # 根据状态过滤
            if status:
                history_list = [record for record in history_list if record.get('status') == status]
        
        return {
            "status": "success",
            "data": {
                "list": history_list,
                "total": len(history_list)
            }
        }
    except Exception as e:
        logger.error(f"搜索历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索历史记录失败: {str(e)}")


# 启动应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )
