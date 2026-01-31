#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用项目内示例 TXT 测试多文件批量构建（上传 -> 并行构建 -> 轮询状态）

无需真实 PDF，直接使用 data/examples/*.txt。先跑通此脚本再测真实 PDF。

用法（项目根目录，先启动后端 python run.py）:
  python scripts/test_batch_build_with_sample_txt.py

  可选环境变量:
  - API_BASE: 后端地址，默认 http://localhost:5001
  - BATCH_BUILD_MAX_WORKERS: 并发数（后端读取），默认 4
  - BATCH_BUILD_POLL_TIMEOUT_SEC: 轮询超时秒数，默认 600（长文本+LLM 可能需数分钟）
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

# 项目根目录（脚本在 scripts/ 下）
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
EXAMPLES_DIR = PROJECT_ROOT / "data" / "examples"

BASE = os.getenv("API_BASE", "http://localhost:5001")
POLL_TIMEOUT_SEC = int(os.getenv("BATCH_BUILD_POLL_TIMEOUT_SEC", "600"))


def main():
    # 收集示例 txt 文件（排除 README 等）
    txt_files = sorted(EXAMPLES_DIR.glob("*.txt"))
    txt_files = [p for p in txt_files if p.suffix.lower() == ".txt" and p.name != "README.txt"]
    if not txt_files:
        print(f"[FAIL] 未找到示例 TXT: {EXAMPLES_DIR}")
        sys.exit(1)

    max_workers_hint = os.getenv("BATCH_BUILD_MAX_WORKERS", "4")
    print("=" * 60)
    print("测试：项目内示例 TXT 多文件批量构建（并行）")
    print("=" * 60)
    print(f"  示例目录: {EXAMPLES_DIR}")
    print(f"  文件数: {len(txt_files)}")
    for i, p in enumerate(txt_files, 1):
        print(f"     [{i}] {p.name}")
    print(f"  后端: {BASE}")
    print(f"  并发: BATCH_BUILD_MAX_WORKERS={max_workers_hint}（后端生效）")
    print(f"  轮询超时: {POLL_TIMEOUT_SEC}s（长文本+LLM 可能需数分钟）")
    print()

    # 1. 批量上传
    print("[1/3] POST /api/hadoop/upload/batch ...")
    try:
        files_list = []
        for path in txt_files:
            files_list.append(
                ("files", (path.name, open(path, "rb"), "text/plain; charset=utf-8"))
            )
        r = requests.post(
            f"{BASE}/api/hadoop/upload/batch",
            files=files_list,
            timeout=60,
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
    if not task_id:
        print("[3/3] 无 task_id，跳过轮询")
        print("=" * 60)
        sys.exit(0)

    print("[3/3] GET /api/hadoop/status/{id} 轮询 ...")
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
        # 每 5 秒或状态变化时打印，避免刷屏
        if (i + 1) % 5 == 0 or i == 0 or str(status).upper() in ("COMPLETED", "FAILED", "SUCCESS", "FINISHED", "ERROR"):
            print(f"    [{i+1}s] status={status}, progress={progress}%, {msg}")
        if str(status).upper() in ("COMPLETED", "SUCCESS", "FINISHED"):
            print(f"  [OK] 构建完成: 实体 {task.get('entities_created', 0)}, 关系 {task.get('relations_created', 0)}")
            file_results = task.get("file_results") or []
            if file_results:
                for fr in file_results:
                    fid_short = (fr.get("file_id") or "")[:8]
                    print(f"        - {fid_short}...: graph_id={fr.get('graph_id')}, entities={fr.get('entities_created', 0)}, relations={fr.get('relations_created', 0)}")
            break
        if str(status).upper() in ("FAILED", "ERROR"):
            print(f"  [FAIL] 构建失败: {msg}")
            if task.get("error_message"):
                print(f"        error: {task.get('error_message')[:300]}")
            sys.exit(1)
    else:
        print(f"  [WARN] 轮询超时（{POLL_TIMEOUT_SEC}s），请在后端或 GET /api/hadoop/status/{task_id} 查看最终结果")

    print("=" * 60)
    print("示例 TXT 批量构建测试完成。通过后可再用真实 PDF 测试。")
    print("=" * 60)


if __name__ == "__main__":
    main()
