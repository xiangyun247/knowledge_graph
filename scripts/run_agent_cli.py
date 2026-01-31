#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph Agent 本地运行脚本

用法（项目根目录）:
  python scripts/run_agent_cli.py
  python scripts/run_agent_cli.py "胰腺炎有哪些症状？"

需要环境变量: DEEPSEEK_API_KEY（可选 DEEPSEEK_BASE_URL, DEEPSEEK_MODEL）
"""

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("请设置环境变量 DEEPSEEK_API_KEY 后再运行。", file=sys.stderr)
        sys.exit(1)
    question = (sys.argv[1] if len(sys.argv) > 1 else "胰腺炎有哪些症状？").strip()
    from backend.agent import run_agent
    print("问题:", question)
    print("-" * 50)
    out = run_agent(question)
    print("回答:", out.get("answer", ""))
    if out.get("sources"):
        print("-" * 50)
        print("来源 (sources):")
        for s in out["sources"]:
            c = s.get("content", "")
            c = c[:200] + "…" if len(c) > 200 else c
            print("  [%s] %s" % (s.get("type", ""), c))

if __name__ == "__main__":
    main()
