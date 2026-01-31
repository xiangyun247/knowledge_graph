#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
6.1 短期记忆：按 session_id 存储近期多轮对话

- 内存存储；可扩展为 Redis（REDIS_URL）
- 每 session 最多 MAX_MESSAGES 条（user+assistant 成对），超出从头部淘汰
"""

import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MAX_MESSAGES = 10  # 约 5 轮
_sessions: Dict[str, List[Dict[str, str]]] = {}


def _redis_client():
    """若配置 REDIS_URL 则返回 redis 客户端，否则 None。"""
    url = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
    if not url:
        return None
    try:
        import redis
        r = redis.from_url(url, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        logger.warning("Redis 不可用: %s，使用内存存储", e)
    return None


def get_session_history(session_id: str) -> List[Dict[str, str]]:
    """
    获取会话历史，每项 {role: "user"|"assistant", content: str}。
    最多 MAX_MESSAGES 条，按时间从旧到新。
    """
    if not session_id or not session_id.strip():
        return []
    rid = _redis_client()
    if rid:
        try:
            raw = rid.get(f"agent:session:{session_id.strip()}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("Redis get_session_history 失败: %s", e)
        return []
    return list(_sessions.get(session_id.strip(), []))


def append_session_exchange(session_id: str, user_content: str, assistant_content: str) -> None:
    """追加一轮 user+assistant，并修剪到 MAX_MESSAGES。"""
    if not session_id or not session_id.strip():
        return
    key = session_id.strip()
    rid = _redis_client()
    if rid:
        try:
            raw = rid.get(f"agent:session:{key}") or "[]"
            arr = json.loads(raw)
            arr.append({"role": "user", "content": user_content or ""})
            arr.append({"role": "assistant", "content": assistant_content or ""})
            arr = arr[-MAX_MESSAGES:]
            rid.set(f"agent:session:{key}", json.dumps(arr, ensure_ascii=False))
            return
        except Exception as e:
            logger.warning("Redis append_session_exchange 失败: %s", e)
            return
    if key not in _sessions:
        _sessions[key] = []
    _sessions[key].append({"role": "user", "content": user_content or ""})
    _sessions[key].append({"role": "assistant", "content": assistant_content or ""})
    _sessions[key] = _sessions[key][-MAX_MESSAGES:]
