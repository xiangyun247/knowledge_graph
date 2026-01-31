#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat（Agent）可用性自检

在项目根目录运行: python scripts/check_agent_ready.py

- 若导入失败：即 /api/agent/query 返回 503 的根因，需安装 langgraph、langchain-openai、langchain-core 或解决报错。
- 若导入成功、调用失败：即运行时报 500 的根因，多为 DEEPSEEK_API_KEY 未配置/无效、网络或 LLM 服务异常。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 加载 .env（与 run.py / config 一致）
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
if not os.getenv("DEEPSEEK_API_KEY"):
    print("[WARN] .env 中未找到 DEEPSEEK_API_KEY，调用 LLM 可能失败。")

def main():
    print("=" * 60)
    print("Chat（Agent）可用性检查")
    print("=" * 60)

    # 1. 导入
    try:
        from backend.agent import run_agent
        print("[OK] 导入 backend.agent.run_agent 成功")
    except Exception as e:
        print("[FAIL] 导入失败（对应 /api/agent/query 的 503）：")
        print("  ", type(e).__name__, ":", e)
        print("\n建议: pip install langgraph langchain-openai langchain-core")
        import traceback
        traceback.print_exc()
        return 1

    # 2. 调用
    try:
        out = run_agent("你好", user_id="1")
        ans = (out.get("answer") or "").strip()
        if not ans:
            print("[WARN] run_agent 返回空 answer，请检查 LLM 与 Tools。")
        else:
            print("[OK] run_agent 调用成功，answer 前 80 字:", ans[:80], "…" if len(ans) > 80 else "")
        print("=" * 60)
        return 0
    except Exception as e:
        print("[FAIL] run_agent 调用失败（对应运行时的 500）：")
        print("  ", type(e).__name__, ":", e)
        print("\n建议: 检查 .env 中 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL 及网络。")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
