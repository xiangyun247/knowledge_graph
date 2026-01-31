#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用真实文件测试 /api/upload 与 /api/kg/build

用法（项目根目录，先启动后端 python run.py）:
  python scripts/test_kg_build_with_real_file.py "C:/Users/23035/Desktop/pdf_test1.pdf"
  python scripts/test_kg_build_with_real_file.py "C:/path/to/your.pdf"

流程: 1) POST /api/upload 上传文件 -> file_id  2) POST /api/kg/build { file_id }  3) 轮询 GET /api/kg/build/progress/{task_id}
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


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/test_kg_build_with_real_file.py <文件路径>")
        print("例:   python scripts/test_kg_build_with_real_file.py \"C:\\Users\\23035\\Desktop\\pdf_test1.pdf\"")
        sys.exit(1)

    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"[FAIL] 文件不存在: {path}")
        sys.exit(1)

    print("=" * 60)
    print("测试 /api/upload -> /api/kg/build（真实文件）")
    print("=" * 60)
    print(f"  文件: {path}")
    print(f"  后端: {BASE}")
    print()

    # 1. 上传
    print("[1/3] POST /api/upload ...")
    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"{BASE}/api/upload",
                files={"file": (path.name, f, "application/pdf") if path.suffix.lower() == ".pdf" else (path.name, f)},
                headers={"X-User-Id": "1"},
                timeout=120,
            )
    except Exception as e:
        print(f"  [FAIL] 请求异常: {e}")
        sys.exit(1)

    if r.status_code != 200:
        print(f"  [FAIL] 状态 {r.status_code}: {r.text[:400]}")
        sys.exit(1)

    data = r.json()
    file_id = data.get("file_id") or data.get("fileId")
    if not file_id:
        print(f"  [FAIL] 响应中无 file_id: {data}")
        sys.exit(1)
    print(f"  [OK] file_id={file_id}")

    # 2. 触发构建
    print("[2/3] POST /api/kg/build ...")
    try:
        r2 = requests.post(
            f"{BASE}/api/kg/build",
            json={"file_id": file_id},
            headers={"Content-Type": "application/json", "X-User-Id": "1"},
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

    # 3. 轮询进度（可选）
    if task_id:
        print("[3/3] GET /api/kg/build/progress/{id} 轮询 ...")
        for i in range(30):
            time.sleep(1)
            try:
                r3 = requests.get(f"{BASE}/api/kg/build/progress/{task_id}", headers={"X-User-Id": "1"}, timeout=10)
            except Exception as e:
                print(f"  轮询异常: {e}")
                continue
            if r3.status_code != 200:
                print(f"  进度接口 {r3.status_code}: {r3.text[:200]}")
                continue
            p = r3.json()
            status = p.get("status", "")
            progress = p.get("progress", 0)
            msg = p.get("message", "")
            print(f"    [{i+1}s] status={status}, progress={progress}%, {msg}")
            if status in ("completed", "COMPLETED", "finished"):
                print(f"  [OK] 构建完成: 实体 {p.get('entities_created', 0)}, 关系 {p.get('relations_created', 0)}")
                break
            if status in ("failed", "FAILED"):
                print(f"  [FAIL] 构建失败: {msg}")
                sys.exit(1)
        else:
            print("  [WARN] 轮询超时，请在后端或 /api/graph/list 查看结果")

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
