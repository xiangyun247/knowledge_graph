#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档知识库（Chroma）可用性自检

在项目根目录运行: python scripts/check_kb_chroma_ready.py

- 若 chromadb 导入失败且提示 np.float_ / NumPy 2.0：请执行 pip install 'numpy<2'
- 若 chromadb 未安装：pip install chromadb 'numpy<2'
- 若 ChromaStore 或 search/list 失败：查看脚本输出的具体错误。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def main():
    print("=" * 60)
    print("文档知识库（Chroma）可用性检查")
    print("=" * 60)

    # 1. numpy 版本
    try:
        import numpy as np
        v = getattr(np, "__version__", "?")
        major = int(v.split(".")[0]) if v and v[0].isdigit() else 0
        if major >= 2:
            print(f"[WARN] numpy {v} 与 chromadb 0.4.x 不兼容（np.float_ 已移除）")
            print("       建议: pip install 'numpy<2'")
        else:
            print(f"[OK]   numpy {v} (兼容 chromadb)")
    except Exception as e:
        print("[FAIL] numpy 检查失败:", e)
        return 1

    # 2. chromadb 导入
    try:
        import chromadb
        print(f"[OK]   chromadb 导入成功 (版本: {getattr(chromadb, '__version__', '?')})")
    except Exception as e:
        err = str(e)
        print("[FAIL] chromadb 导入失败:")
        print("  ", err)
        if "np.float_" in err or "NumPy 2.0" in err or "numpy" in err.lower():
            print("\n建议: pip install 'numpy<2'  然后重试")
        else:
            print("\n建议: pip install chromadb 'numpy<2'")
        return 1

    # 3. ChromaStore 初始化（不触发 Embedding，只验证 chroma 连接与集合）
    try:
        from backend.chroma_store import ChromaStore
        store = ChromaStore()
        _ = store._collection.count()
        print("[OK]   ChromaStore 初始化成功，集合可访问")
    except Exception as e:
        print("[FAIL] ChromaStore 初始化失败:")
        print("  ", type(e).__name__, ":", e)
        import traceback
        traceback.print_exc()
        return 1

    # 4. get_chunks（list 所用，不需 Embedding）
    try:
        chunks = store.get_chunks(where=None, limit=1)
        print("[OK]   get_chunks（列表底层）可用")
    except Exception as e:
        print("[FAIL] get_chunks 失败:", e)
        return 1

    # 5. search（需要 Embedding，首次会加载 sentence-transformers，可能较慢）
    try:
        hits = store.search(query_text="测试", k=1, where=None)
        print("[OK]   search（检索）可用，返回", len(hits), "条")
    except Exception as e:
        print("[FAIL] search 失败（可能为 Embedding 未就绪）:")
        print("  ", type(e).__name__, ":", e)
        print("  建议: 确认 sentence-transformers 已安装、numpy<2；或配置 OPENAI 类 Embedding API")
        return 1

    print("=" * 60)
    print("文档知识库（Chroma）检查通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
