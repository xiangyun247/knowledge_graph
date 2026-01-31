#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7.1 Agent 请求上下文的 user_id

在 agent_router 中从 get_current_user_id 取得 user_id，写入 contextvar；
run_agent / run_agent_stream 接受 user_id 参数并在入口设置，供 tools 读取。
"""

import contextvars
from typing import Optional

_agent_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_user_id", default=None
)


def set_agent_user_id(user_id: Optional[str]) -> None:
    _agent_user_id.set(user_id)


def get_agent_user_id() -> Optional[str]:
    return _agent_user_id.get()
