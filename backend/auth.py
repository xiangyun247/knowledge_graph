#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JWT 认证与角色权限

- 解析 Authorization Bearer 获取 user_id、role
- 提供 create_access_token / create_refresh_token / decode_token
- 提供 get_current_user、get_current_user_id、require_roles 装饰器
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import jwt
from fastapi import Request, HTTPException, Depends
from pydantic import BaseModel

# 从环境变量读取，未配置时使用默认值（生产环境务必设置 JWT_SECRET）
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALG = "HS256"


def _validate_jwt_secret_for_production() -> None:
    """生产环境下校验 JWT_SECRET，禁止使用默认值。"""
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        if not JWT_SECRET or JWT_SECRET == "change-me-in-production" or len(JWT_SECRET) < 32:
            raise ValueError(
                "生产环境必须设置 JWT_SECRET（至少 32 位强随机字符串），"
                "且不能使用默认值 change-me-in-production"
            )
ACCESS_EXPIRES_SEC = int(os.getenv("JWT_ACCESS_EXPIRES", "3600"))  # 1 小时
REFRESH_EXPIRES_SEC = int(os.getenv("JWT_REFRESH_EXPIRES", "604800"))  # 7 天

# JWT payload 中的 claim 名
CLAIM_SUB = "sub"  # user_id
CLAIM_ROLE = "role"
CLAIM_TYPE = "type"  # "access" | "refresh"


class TokenPair(BaseModel):
    """登录/刷新返回的 token 对"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = ACCESS_EXPIRES_SEC


def create_access_token(user_id: str, role: str = "patient") -> str:
    """生成 Access Token（短期，用于 API 请求）。"""
    now = datetime.utcnow()
    payload = {
        CLAIM_SUB: user_id,
        CLAIM_ROLE: role,
        CLAIM_TYPE: "access",
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_EXPIRES_SEC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_refresh_token(user_id: str, role: str = "patient") -> str:
    """生成 Refresh Token（长期，仅用于换取新 access_token）。"""
    now = datetime.utcnow()
    payload = {
        CLAIM_SUB: user_id,
        CLAIM_ROLE: role,
        CLAIM_TYPE: "refresh",
        "iat": now,
        "exp": now + timedelta(seconds=REFRESH_EXPIRES_SEC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT，失败返回 None。"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload
    except jwt.PyJWTError:
        return None


def get_current_user(request: Request) -> Tuple[str, str]:
    """
    从请求中解析当前用户 id 与角色。

    优先级：Authorization Bearer JWT > X-User-Id 请求头 > default_user

    Returns:
        (user_id, role)
    """
    auth = request.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            payload = decode_token(token)
            if payload and payload.get(CLAIM_TYPE) == "access":
                uid = payload.get(CLAIM_SUB)
                role = payload.get(CLAIM_ROLE) or "patient"
                if uid:
                    return str(uid), str(role)
            # Token 存在但无效或已过期，返回 401 供前端刷新
            raise HTTPException(
                status_code=401,
                detail={"code": "E_TOKEN_EXPIRED", "message": "Token 无效或已过期"},
            )

    # 回退：X-User-Id（兼容旧前端）
    uid = (request.headers.get("X-User-Id") or "").strip()
    if uid:
        return uid, "patient"

    # 未认证用户，角色为 guest，仅能浏览
    return "default_user", "guest"


def get_current_user_id(request: Request) -> str:
    """获取当前用户 id，用于 KB、图谱、Agent 的权限过滤。"""
    user_id, _ = get_current_user(request)
    return user_id


def require_roles(*roles: str):
    """
    FastAPI 依赖：要求当前用户角色在 roles 中，否则返回 403。

    用法：
        @app.post("/api/kg/build", dependencies=[require_roles("admin", "teacher", "student")])
        async def build_kg(req: Request, body: BuildKGFromFileRequest):
            ...
    """
    allowed = set(roles)

    async def _dep(request: Request) -> None:
        _, role = get_current_user(request)
        if role not in allowed:
            raise HTTPException(
                status_code=403,
                detail={"code": "E_FORBIDDEN", "message": f"需要角色: {', '.join(sorted(roles))}"},
            )

    return Depends(_dep)
