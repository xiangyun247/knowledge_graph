#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端端到端烟雾测试

不启动 HTTP 服务，用 FastAPI TestClient 直接调用 backend.app，
验证主要接口可访问、返回合理状态码，便于在对接前端前先跑通后端。

运行（项目根目录）:
  python scripts/run_backend_smoke.py

依赖:
  - .env 至少配置 NEO4J_PASSWORD（Neo4j 可宕机，会回退 MySQL）
  - 可选: MYSQL_*、DEEPSEEK_API_KEY；Chroma 需 numpy<2（与 NumPy 2.0 不兼容）
  - pip install -r requirements.txt 或 pip install loguru neo4j pymysql sqlalchemy fastapi python-dotenv

通过条件:
  - 200，或约定的 404/503/500（任务不存在 404；Agent/旧 RAG 不可用时 503；KB 在 Chroma 异常时 500 亦算通过）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 1. 加载 .env（必须先于会 import config 的模块）
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
_env = ROOT / ".env"
if _env.exists():
    load_dotenv(_env, override=True)
else:
    load_dotenv(ROOT / ".env.example", override=False)

# 2. 项目根加入 path
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 3. 提前检查 NEO4J_PASSWORD（config 会强制校验）
if not os.getenv("NEO4J_PASSWORD"):
    print("[WARN] NEO4J_PASSWORD 未设置，导入 backend 时可能因 config 校验失败退出。")
    print("       请复制 .env.example 为 .env 并填写 NEO4J_PASSWORD。")

# 4. 导入 app 与 TestClient
try:
    from fastapi.testclient import TestClient
    from backend.app import app
except Exception as e:
    print(f"[FAIL] 导入 backend.app 失败: {e}")
    print("       若为 NEO4J_PASSWORD / config 相关，请检查 .env。")
    sys.exit(1)

client = TestClient(app, raise_server_exceptions=False)


def _ok(name: str, res, accept: list[int] | None = None) -> bool:
    """通过：200 或 accept 中的状态码。"""
    acc = accept or []
    if res.status_code == 200 or res.status_code in acc:
        print(f"  [OK]   {name} -> {res.status_code}")
        return True
    body = (res.text or "")[:300]
    print(f"  [FAIL] {name} -> {res.status_code}  body={body}")
    return False


def main() -> int:
    print("=" * 60)
    print("后端端到端烟雾测试 (TestClient, backend.app)")
    print("=" * 60)

    n, passed = 0, 0

    # A. 文档/OpenAPI
    n += 1
    r = client.get("/docs")
    if _ok("GET /docs", r):
        passed += 1

    # B. 图谱列表
    n += 1
    r = client.get("/api/graph/list")
    if _ok("GET /api/graph/list", r):
        passed += 1

    # C. 知识库列表（无 X-User-Id 时用 default_user；Chroma/NumPy 不兼容时可能 500）
    n += 1
    r = client.get("/api/kb/documents/list")
    if _ok("GET /api/kb/documents/list", r, accept=[500]):
        passed += 1
    if r.status_code == 500 and "np.float_" in (r.text or ""):
        print("       [HINT] 若为 np.float_/NumPy 2.0，请: pip install 'numpy<2' 或升级 chromadb")

    # D. 知识库检索（Chroma 不可用时可能 500）
    n += 1
    r = client.get("/api/kb/documents/search", params={"q": "test", "k": 1})
    if _ok("GET /api/kb/documents/search", r, accept=[500]):
        passed += 1

    # E. 任务进度（不存在的 task_id -> 404）
    n += 1
    r = client.get("/api/kg/build/progress/00000000-0000-0000-0000-000000000001")
    if _ok("GET /api/kg/build/progress/{fake_id}", r, accept=[404]):
        passed += 1

    # F. Agent 问答（200=成功；503=Agent 不可用；500=LLM/依赖失败 均视为路由通）
    n += 1
    r = client.post(
        "/api/agent/query",
        json={"question": "你好", "session_id": None},
        headers={"X-User-Id": "test_user"},
    )
    if _ok("POST /api/agent/query", r, accept=[503, 500]):
        passed += 1

    # G. 旧 RAG 查询
    n += 1
    r = client.post("/api/query", json={"question": "你好", "max_results": 5})
    if _ok("POST /api/query", r, accept=[503, 500]):
        passed += 1

    # H. Hadoop 任务列表
    n += 1
    r = client.get("/api/hadoop/tasks")
    if _ok("GET /api/hadoop/tasks", r):
        passed += 1

    # I. 文档入库：file_id 不存在 -> 404（仅验证路由与 7.1 权限注入）
    n += 1
    r = client.post(
        "/api/kb/documents/ingest",
        data={"file_id": "00000000-0000-0000-0000-000000000000", "strategy": "fixed"},
        headers={"X-User-Id": "test_user"},
    )
    if _ok("POST /api/kb/documents/ingest (file_id 不存在)", r, accept=[404]):
        passed += 1

    # J. 历史记录列表
    n += 1
    r = client.get("/api/history/list")
    if _ok("GET /api/history/list", r):
        passed += 1

    print("=" * 60)
    print(f"通过: {passed}/{n}")
    print("=" * 60)
    return 0 if passed == n else 1


if __name__ == "__main__":
    sys.exit(main())
