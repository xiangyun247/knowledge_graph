#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_cognitive_load.py

从 MySQL 读取 cognitive_events / cognitive_questionnaires，输出简单统计：
- 不同 source/view_mode（长文/step/card）下的平均 duration_ms / 样本数
- Chat 普通回答 vs 简洁回答的平均 duration_ms / 平均主观分

用法：
    python scripts/analyze_cognitive_load.py              # 默认统计近 7 天
    python scripts/analyze_cognitive_load.py 14           # 统计近 14 天

说明：
- 脚本仅用于线下分析与报告撰写，不作为正式 API 部署；
- 依赖 db/mysql_client.get_mysql_client，请确保 .env 中 MySQL 相关配置正确。
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.mysql_client import get_mysql_client  # noqa: E402


def _fmt_ms(ms: float) -> str:
    """格式化毫秒为字符串（保留 1 位小数）。"""
    try:
        return f"{ms:.1f}"
    except Exception:
        return str(ms)


def analyze(days: int = 7) -> None:
    client = get_mysql_client()
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    since_ts = now_ms - days * 24 * 3600 * 1000

    print(f"=== 近 {days} 天任务结束耗时统计（按 source / view_mode） ===")

    # 1) 从 cognitive_events 中取出 task_end 事件
    params: Dict[str, Any] = {"since_ts": since_ts}
    rows = client.execute_query(
        """
        SELECT user_id, source, event_type, ts, params_json
        FROM cognitive_events
        WHERE ts >= :since_ts AND event_type = 'task_end'
        """,
        params,
    )

    # buckets: (source, view_mode, concise_flag) -> list[duration_ms]
    buckets = {}
    total_events = len(rows)
    for r in rows:
        src = (r.get("source") or "").strip() or "unknown"
        p = r.get("params_json") or {}
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except Exception:
                p = {}
        # view_mode 主要用于患者教育：long/step/card
        view_mode = p.get("view_mode") or "unknown"
        # concise 标记主要用于 Chat：简洁回答 vs 普通回答
        concise_flag = "concise" if p.get("answer_style") == "concise" or p.get("concise") else "normal"

        dur = p.get("duration_ms") or p.get("duration") or 0
        try:
            dur = float(dur)
        except Exception:
            continue
        if dur <= 0:
            continue

        key = (src, view_mode, concise_flag)
        buckets.setdefault(key, []).append(dur)

    if not buckets:
        print("暂无 task_end 事件数据。")
    else:
        for (src, vm, concise), ds in sorted(buckets.items()):
            avg = sum(ds) / len(ds)
            label = f"{src} / {vm}"
            if src == "chat":
                label += f" / {'简洁回答' if concise == 'concise' else '普通回答'}"
            print(f"{label}: n={len(ds)}, avg={_fmt_ms(avg)} ms")

    # 2) 问卷统计（整体 + 按 source 简单拆分）
    print("\n=== 问卷总体平均分（所有题目的整体均值） ===")

    q_rows = client.execute_query(
        """
        SELECT source, answers_json
        FROM cognitive_questionnaires
        WHERE ts >= :since_ts
        """,
        {"since_ts": since_ts},
    )

    if not q_rows:
        print("暂无问卷数据。")
        return

    total_answers = 0
    total_score = 0.0

    # 按 source 聚合，用于简单查看 patient_education/chat 差异
    by_source = {}

    for r in q_rows:
        src = (r.get("source") or "").strip() or "unknown"
        answers = r.get("answers_json") or []
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except Exception:
                answers = []
        for a in answers:
            v = a.get("value")
            try:
                v = float(v)
            except Exception:
                continue
            total_answers += 1
            total_score += v
            agg = by_source.setdefault(src, {"sum": 0.0, "cnt": 0})
            agg["sum"] += v
            agg["cnt"] += 1

    if total_answers:
        print(f"总答案样本 {total_answers}，整体均值 {total_score / total_answers:.2f}")
    else:
        print("暂无有效评分数据。")

    print("\n=== 按 source 维度的平均主观得分 ===")
    for src, agg in by_source.items():
        if agg["cnt"]:
            print(f"{src}: n={agg['cnt']}, avg={agg['sum'] / agg['cnt']:.2f}")


def main(argv=None):
    argv = argv or sys.argv[1:]
    try:
        days = int(argv[0]) if argv else 7
    except Exception:
        days = 7
    if days <= 0:
        days = 7
    analyze(days)


if __name__ == "__main__":
    main()

