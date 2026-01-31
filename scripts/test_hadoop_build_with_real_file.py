#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用真实文件测试 /api/hadoop/upload/batch 与 /api/hadoop/build/batch（并行构建）

用法（项目根目录，先启动后端 python run.py）:
  单文件: python scripts/test_hadoop_build_with_real_file.py "C:/path/to/a.pdf"
  多文件: python scripts/test_hadoop_build_with_real_file.py a.pdf b.pdf c.pdf

  并发数: BATCH_BUILD_MAX_WORKERS（默认 4）
  轮询超时: BATCH_BUILD_POLL_TIMEOUT_SEC（默认 600 秒，长文本+LLM 可能需数分钟）

流程:
  1) POST /api/hadoop/upload/batch 上传文件 -> uploaded_file_ids
  2) POST /api/hadoop/build/batch { file_ids, use_hadoop: true }（后端并行构建）
  3) 轮询 GET /api/hadoop/status/{task_id}
"""

import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("请先安装: pip install requests")
    sys.exit(1)

BASE = os.getenv("API_BASE", "http://localhost:5001")
POLL_TIMEOUT_SEC = int(os.getenv("BATCH_BUILD_POLL_TIMEOUT_SEC", "600"))


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/test_hadoop_build_with_real_file.py <文件路径> [文件2 文件3 ...]")
        print("例:   python scripts/test_hadoop_build_with_real_file.py a.pdf b.pdf")
        print("提示: 可设置 BATCH_BUILD_MAX_WORKERS=2 控制批量构建并发数（默认 4）")
        sys.exit(1)

    paths = []
    for p in sys.argv[1:]:
        path = Path(p).resolve()
        if not path.is_file():
            print(f"[FAIL] 文件不存在: {path}")
            sys.exit(1)
        paths.append(path)

    max_workers_hint = os.getenv("BATCH_BUILD_MAX_WORKERS", "4")
    print("=" * 60)
    print("测试 /api/hadoop/upload/batch -> /api/hadoop/build/batch（并行构建）")
    print("=" * 60)
    print(f"  文件数: {len(paths)}")
    for i, p in enumerate(paths, 1):
        print(f"     [{i}] {p.name}")
    print(f"  后端: {BASE}")
    print(f"  并发数: BATCH_BUILD_MAX_WORKERS={max_workers_hint}（后端生效）")
    print()

    # 1. 批量上传
    print("[1/3] POST /api/hadoop/upload/batch ...")
    try:
        files_list = []
        for path in paths:
            ct = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
            files_list.append(("files", (path.name, open(path, "rb"), ct)))
        r = requests.post(
            f"{BASE}/api/hadoop/upload/batch",
            files=files_list,
            timeout=120,
        )
        for _name, (_fname, fh, _ct) in files_list:
            fh.close()
    except Exception as e:
        print(f"  [FAIL] 请求异常: {e}")
        sys.exit(1)

    if r.status_code != 200:
        print(f"  [FAIL] 状态 {r.status_code}: {r.text[:500]}")
        sys.exit(1)

    data = r.json()
    file_ids = data.get("uploaded_file_ids") or []
    if not file_ids:
        print(f"  [FAIL] 响应中无 uploaded_file_ids: {data}")
        sys.exit(1)
    print(f"  [OK] uploaded_file_ids={file_ids} (共 {len(file_ids)} 个)")

    # 2. 触发批量构建
    print("[2/3] POST /api/hadoop/build/batch ...")
    try:
        r2 = requests.post(
            f"{BASE}/api/hadoop/build/batch",
            json={"file_ids": file_ids, "use_hadoop": True},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except Exception as e:
        print(f"  [FAIL] 请求异常: {e}")
        sys.exit(1)

    if r2.status_code != 200:
        print(f"  [FAIL] 状态 {r2.status_code}: {r2.text[:500]}")
        sys.exit(1)

    data2 = r2.json()
    task_id = data2.get("task_id")
    if not task_id:
        print(f"  [WARN] 响应中无 task_id: {data2}")
    else:
        print(f"  [OK] task_id={task_id}")

    # 3. 轮询状态
    if task_id:
        print(f"[3/3] GET /api/hadoop/status/{task_id} 轮询（超时 {POLL_TIMEOUT_SEC}s）...")
        for i in range(POLL_TIMEOUT_SEC):
            time.sleep(1)
            try:
                r3 = requests.get(f"{BASE}/api/hadoop/status/{task_id}", timeout=10)
            except Exception as e:
                print(f"  轮询异常: {e}")
                continue
            if r3.status_code != 200:
                print(f"  状态接口 {r3.status_code}: {r3.text[:200]}")
                continue
            p = r3.json()
            task = p.get("task") or p
            status = task.get("status", "")
            progress = task.get("progress", 0)
            msg = task.get("message", "")
            if (i + 1) % 5 == 0 or i == 0 or str(status).upper() in ("COMPLETED", "FAILED", "SUCCESS", "FINISHED", "ERROR"):
                print(f"    [{i+1}s] status={status}, progress={progress}%, {msg}")
            if str(status).upper() in ("COMPLETED", "SUCCESS", "FINISHED"):
                print(f"  [OK] 构建完成: 实体 {task.get('entities_created', 0)}, 关系 {task.get('relations_created', 0)}")
                file_results = task.get("file_results") or []
                if file_results:
                    for fr in file_results:
                        print(f"        - {fr.get('file_id', '')[:8]}...: graph_id={fr.get('graph_id')}, entities={fr.get('entities_created', 0)}, relations={fr.get('relations_created', 0)}")
                break
            if str(status).upper() in ("FAILED", "ERROR"):
                print(f"  [FAIL] 构建失败: {msg}")
                if task.get("error_message"):
                    print(f"        error: {task.get('error_message')[:300]}")
                sys.exit(1)
        else:
            print(f"  [WARN] 轮询超时（{POLL_TIMEOUT_SEC}s），请 GET /api/hadoop/status/{task_id} 查看最终结果")
            print("        若任务长时间停在 90%，多为 kg.builder 的 LLM/Neo4j 调用较慢，可检查 DEEPSEEK_API_KEY、Neo4j 等配置。")

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
