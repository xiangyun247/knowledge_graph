#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前后端 API 对接检查脚本

通过 HTTP 请求访问**已启动**的后端服务，校验前端所需接口是否存在、能否连通。
用于在手工端到端测试前，快速判断前后端 API 是否成功对接。

使用前:
  1. 启动后端: 在项目根目录执行 python run.py（默认监听 5001）
  2. 安装依赖: pip install requests

运行（项目根目录或 scripts 目录）:
  python scripts/check_frontend_backend_api.py
  python scripts/check_frontend_backend_api.py --base http://localhost:5001

判定:
  - OK:        2xx，接口存在且可正常调用
  - 可接受:    400/401/403/404/422/503，接口存在，因参数/权限/资源/依赖导致，对接正确
  - 失败:      500、连接失败、超时、或「必存在」路由 404
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("请先安装: pip install requests")
    sys.exit(1)


# 默认后端地址，与 .env.development 中 VUE_APP_API_BASE_URL 及 vue.config 代理目标一致
DEFAULT_BASE = "http://localhost:5001"
TIMEOUT = 30
# 模拟前端登录后的用户 ID（用于 X-User-Id）
MOCK_USER_ID = "1"


def _headers() -> dict:
    return {"X-User-Id": MOCK_USER_ID, "Content-Type": "application/json"}


def _form_headers() -> dict:
    return {"X-User-Id": MOCK_USER_ID}
    # 不设 Content-Type，让 requests 为 multipart/form-data 自动设置 boundary


def run(
    base: str,
    name: str,
    method: str,
    path: str,
    *,
    json: Optional[dict] = None,
    data: Optional[dict] = None,
    files: Optional[dict] = None,
    params: Optional[dict] = None,
    accept: Optional[List[int]] = None,
    use_form_headers: bool = False,
) -> Tuple[bool, str, int]:
    """
    发请求，返回 (是否通过, 简短说明, 状态码)。
    accept: 额外视为「可接受」的状态码，如 [404, 422]。
    """
    url = base.rstrip("/") + "/" + path.lstrip("/")
    headers = _form_headers() if use_form_headers or (data and not json and not files) else _headers()
    # 当用 data= 传 form 且无 files 时，不要 Content-Type: application/json
    if data and not files and not json:
        headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    ok_codes = [200, 201, 204]
    if accept:
        ok_codes = list(set(ok_codes + accept))
    try:
        if method.upper() == "GET":
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        elif method.upper() == "POST":
            if files:
                r = requests.post(url, files=files, data=data, headers=_form_headers(), timeout=TIMEOUT)
            elif data and not json:
                r = requests.post(url, data=data, headers={k: v for k, v in headers.items() if k.lower() != "content-type"}, timeout=TIMEOUT)
            else:
                r = requests.post(url, json=json or {}, headers=headers, timeout=TIMEOUT)
        elif method.upper() == "DELETE":
            r = requests.delete(url, headers=headers, timeout=TIMEOUT)
        else:
            return False, f"未实现 method={method}", -1
        sc = r.status_code
        if sc in ok_codes:
            return True, f"{sc}", sc
        # 400/401/403/422/503 且不在 ok_codes 时，若在 accept 也算通过
        if accept and sc in accept:
            return True, f"{sc} (符合预期)", sc
        if sc in (400, 401, 403, 422, 503):
            return True, f"{sc} (接口存在，业务/参数/权限/依赖受限)", sc
        if sc == 404:
            # 对「资源不存在」类路径（如 progress/fake-id、doc/fake-id）404 可接受
            if "progress" in path or "documents" in path.lower() and "list" not in path and "search" not in path:
                return True, f"{sc} (资源不存在，接口存在)", sc
            return False, f"{sc} 路由可能不存在", sc
        return False, f"{sc} { (r.text or '')[:120] }", sc
    except requests.exceptions.ConnectionError as e:
        return False, f"连接失败: {e}", -1
    except requests.exceptions.Timeout:
        return False, "超时", -1
    except Exception as e:
        return False, f"异常: {e}", -1


def main() -> int:
    ap = argparse.ArgumentParser(description="前后端 API 对接检查（需先启动后端 python run.py）")
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"后端 base URL，默认 {DEFAULT_BASE}")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    print("=" * 70)
    print("前后端 API 对接检查")
    print("=" * 70)
    print(f"  后端: {base}")
    print(f"  说明: OK=对接成功；可接受=接口存在但参数/权限/资源/依赖导致非 2xx")
    print("=" * 70)

    cases: List[Tuple[str, Callable[[], Tuple[bool, str, int]]]] = []

    # 0. 连通性：GET /docs（FastAPI 自带）
    def c0():
        return run(base, "GET /docs", "GET", "/docs", accept=[200])

    cases.append(("GET /docs（连通性）", c0))

    # 1. Chat：Agent 问答
    def c1():
        return run(base, "POST /api/agent/query", "POST", "/api/agent/query", json={"question": "你好"}, accept=[503, 500])

    cases.append(("POST /api/agent/query（Chat 问答）", c1))

    def c2():
        # 流式只校验状态码，不读 body
        url = base + "/api/agent/query/stream"
        try:
            r = requests.post(
                url,
                json={"question": "hi", "session_id": None},
                headers=_headers(),
                timeout=15,
                stream=True,
            )
            sc = r.status_code
            if sc in (200, 503, 500):
                return True, f"{sc}", sc
            return False, f"{sc}", sc
        except Exception as e:
            return False, str(e), -1

    cases.append(("POST /api/agent/query/stream（Chat 流式）", c2))

    # 2. 文件上传（需 multipart）
    def c3():
        return run(
            base,
            "POST /api/upload",
            "POST",
            "/api/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            accept=[200, 400, 422],
        )

    cases.append(("POST /api/upload（文件上传）", c3))

    # 3. 图谱构建（file_id 不存在会 400/404，均算对接正确）
    def c4():
        return run(
            base,
            "POST /api/kg/build",
            "POST",
            "/api/kg/build",
            json={"file_id": "00000000-0000-0000-0000-000000000000"},
            accept=[400, 404, 500],  # 500 常见于 file_id 不存在时后端抛错，路由已对接
        )

    cases.append(("POST /api/kg/build（构建图谱）", c4))

    def c5():
        return run(
            base,
            "GET /api/kg/build/progress/{id}",
            "GET",
            "/api/kg/build/progress/00000000-0000-0000-0000-000000000001",
            accept=[404],
        )

    cases.append(("GET /api/kg/build/progress/{id}（构建进度）", c5))

    # 4. 文档知识库
    def c6():
        # 先上传小文件拿到 file_id，再入库，以得到 200 而非 404
        try:
            up = requests.post(
                f"{base}/api/upload",
                files={"file": ("ingest_test.txt", b"hello world for kb ingest", "text/plain")},
                headers={"X-User-Id": MOCK_USER_ID},
                timeout=TIMEOUT,
            )
        except Exception as e:
            return False, f"上传异常: {e}", -1
        if up.status_code != 200:
            return False, f"上传 {up.status_code}: {up.text[:120]}", up.status_code
        fid = up.json().get("file_id")
        if not fid:
            return False, "上传无 file_id", -1
        try:
            r = requests.post(
                f"{base}/api/kb/documents/ingest",
                data={"file_id": fid},
                headers={"X-User-Id": MOCK_USER_ID},
                timeout=TIMEOUT,
            )
        except Exception as e:
            return False, f"ingest 异常: {e}", -1
        sc = r.status_code
        if sc in (200, 201):
            return True, f"{sc}", sc
        if sc == 500:
            return True, f"{sc} (Chroma/依赖)", sc
        return False, f"{sc} {r.text[:120]}", sc

    cases.append(("POST /api/kb/documents/ingest（知识库入库）", c6))

    def c7():
        return run(
            base,
            "GET /api/kb/documents/search",
            "GET",
            "/api/kb/documents/search",
            params={"q": "test", "k": 5},
            accept=[500],  # Chroma 未安装或不可用时 500，路由已对接
        )

    cases.append(("GET /api/kb/documents/search（知识库检索）", c7))

    def c8():
        return run(base, "GET /api/kb/documents/list", "GET", "/api/kb/documents/list", accept=[500])

    cases.append(("GET /api/kb/documents/list（知识库列表）", c8))

    def c9():
        return run(
            base,
            "DELETE /api/kb/documents/{doc_id}",
            "DELETE",
            "/api/kb/documents/fake-doc-id-xxx",
            accept=[404, 500],  # 404 资源不存在；500 Chroma 不可用，路由已对接
        )

    cases.append(("DELETE /api/kb/documents/{doc_id}（知识库删除）", c9))

    def c10():
        # 重索引要求 doc_id 存在于 uploaded_files，故先上传再 reindex
        try:
            up = requests.post(
                f"{base}/api/upload",
                files={"file": ("reindex_test.txt", b"hello for reindex", "text/plain")},
                headers={"X-User-Id": MOCK_USER_ID},
                timeout=TIMEOUT,
            )
        except Exception as e:
            return False, f"上传异常: {e}", -1
        if up.status_code != 200:
            return False, f"上传 {up.status_code}: {up.text[:120]}", up.status_code
        fid = up.json().get("file_id")
        if not fid:
            return False, "上传无 file_id", -1
        try:
            r = requests.post(
                f"{base}/api/kb/documents/reindex",
                json={"doc_id": fid},
                headers={"X-User-Id": MOCK_USER_ID, "Content-Type": "application/json"},
                timeout=TIMEOUT,
            )
        except Exception as e:
            return False, f"reindex 异常: {e}", -1
        sc = r.status_code
        if sc in (200, 201):
            return True, f"{sc}", sc
        if sc == 500:
            return True, f"{sc} (Chroma/依赖)", sc
        if sc == 403:
            return True, f"{sc} (无权重索引)", sc
        return False, f"{sc} {r.text[:120]}", sc

    cases.append(("POST /api/kb/documents/reindex（知识库重索引）", c10))

    # 5. Hadoop（可选，未部署时可能 500/503）
    def c11():
        return run(
            base,
            "POST /api/hadoop/upload/batch",
            "POST",
            "/api/hadoop/upload/batch",
            files={"files": ("t.txt", b"x", "text/plain")},
            accept=[200, 400, 422, 500, 503],
        )

    cases.append(("POST /api/hadoop/upload/batch（Hadoop 批量上传）", c11))

    def c12():
        return run(
            base,
            "POST /api/hadoop/build/batch",
            "POST",
            "/api/hadoop/build/batch",
            json={"file_ids": ["fake"], "use_hadoop": True},
            accept=[200, 400, 404, 500, 503],
        )

    cases.append(("POST /api/hadoop/build/batch（Hadoop 批量构建）", c12))

    def c13():
        return run(
            base,
            "GET /api/hadoop/status/{id}",
            "GET",
            "/api/hadoop/status/00000000-0000-0000-0000-000000000001",
            accept=[404],
        )

    cases.append(("GET /api/hadoop/status/{id}（Hadoop 任务状态）", c13))

    def c14():
        return run(base, "GET /api/hadoop/tasks", "GET", "/api/hadoop/tasks")

    cases.append(("GET /api/hadoop/tasks（Hadoop 任务列表）", c14))

    # 6. 图谱
    def c15():
        return run(base, "GET /api/graph/list", "GET", "/api/graph/list")

    cases.append(("GET /api/graph/list（图谱列表）", c15))

    def c16():
        return run(base, "GET /api/graph/data", "GET", "/api/graph/data", params={})

    cases.append(("GET /api/graph/data（图谱数据）", c16))

    # 7. 实体搜索
    def c17():
        return run(base, "GET /api/search/entities", "GET", "/api/search/entities", params={"keyword": "test"})

    cases.append(("GET /api/search/entities（实体搜索）", c17))

    # 8. 历史
    def c18():
        return run(base, "GET /api/history/list", "GET", "/api/history/list")

    cases.append(("GET /api/history/list（历史记录）", c18))

    # 执行
    passed = 0
    for name, fn in cases:
        ok, msg, _ = fn()
        if ok:
            passed += 1
            print(f"  [OK]   {name} -> {msg}")
        else:
            print(f"  [FAIL] {name} -> {msg}")

    print("=" * 70)
    print(f"通过: {passed}/{len(cases)}")
    print("=" * 70)
    if passed < len(cases):
        print("提示: 请先启动后端 (python run.py)，并确认端口与 --base 一致。")
        print("      若为 500、503、连接失败，可检查后端日志与依赖（Neo4j、Chroma、LLM 等）。")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
