#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
7.1 权限与多租户：当前用户识别

- 优先从请求头 X-User-Id 取值（前端登录后设置）
- 若后续接入 JWT，可从此扩展：解析 Authorization Bearer 的 user_id/sub
- 否则回退为 default_user，保证单机/未登录时可运行
"""

from fastapi import Request


def get_current_user_id(request: Request) -> str:
    """
    从请求中解析当前用户 id，用于 KB、图谱、Agent 的权限过滤。

    优先级：X-User-Id 请求头 > (未来) JWT sub/user_id > "default_user"
    """
    uid = (request.headers.get("X-User-Id") or "").strip()
    if uid:
        return uid
    # 若后续接 JWT: 解析 Authorization Bearer, 取 sub 或 user_id
    return "default_user"
