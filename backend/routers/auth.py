#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证API路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from datetime import datetime
import bcrypt
import uuid

from backend.auth import (
    get_current_user_id,
    get_current_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    require_roles,
    ACCESS_EXPIRES_SEC
)
from db.mysql_client import get_mysql_client
from loguru import logger

router = APIRouter(prefix="/api/auth", tags=["认证"])


def get_mysql():
    try:
        return get_mysql_client()
    except:
        return None


def _ensure_users_table():
    mysql = get_mysql()
    if not mysql:
        return
    try:
        mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(64) PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                role VARCHAR(32) DEFAULT 'patient',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception as e:
        logger.warning(f"创建users表失败: {e}")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except:
        return False


def _get_user_by_username(username: str):
    mysql = get_mysql()
    if not mysql:
        return None
    try:
        result = mysql.execute_query(
            "SELECT * FROM users WHERE username = :username",
            {"username": username}
        )
        return result[0] if result else None
    except:
        return None


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "patient"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UpdateRoleRequest(BaseModel):
    user_id: str
    role: str


@router.post("/register")
async def register_user(body: RegisterRequest):
    """用户注册"""
    _ensure_users_table()

    mysql = get_mysql()
    if not mysql:
        raise HTTPException(status_code=500, detail="MySQL未配置")

    try:
        existing = _get_user_by_username(body.username)
        if existing:
            raise HTTPException(status_code=400, detail="用户名已存在")

        user_id = str(uuid.uuid4())
        password_hash = _hash_password(body.password)

        mysql.execute_update(
            "INSERT INTO users (id, username, password_hash, role) VALUES (:id, :username, :hash, :role)",
            {"id": user_id, "username": body.username, "hash": password_hash, "role": body.role}
        )

        access_token = create_access_token(data={"sub": user_id, "username": body.username, "role": body.role})
        refresh_token = create_refresh_token(data={"sub": user_id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user_id,
            "username": body.username,
            "role": body.role
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/login")
async def login_user(body: LoginRequest):
    """用户登录"""
    user = _get_user_by_username(body.username)
    if not user or not _verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token = create_access_token(
        data={"sub": user["id"], "username": user["username"], "role": user.get("role", "patient")}
    )
    refresh_token = create_refresh_token(data={"sub": user["id"]})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "patient")
    }


@router.post("/refresh")
async def refresh_token(body: RefreshTokenRequest):
    """刷新Token"""
    try:
        payload = decode_token(body.refresh_token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的refresh_token")

        user_id = payload.get("sub")
        mysql = get_mysql()

        if mysql:
            result = mysql.execute_query(
                "SELECT * FROM users WHERE id = :id",
                {"id": user_id}
            )
            if not result:
                raise HTTPException(status_code=401, detail="用户不存在")
            user = result[0]
        else:
            raise HTTPException(status_code=500, detail="MySQL未配置")

        access_token = create_access_token(
            data={"sub": user["id"], "username": user["username"], "role": user.get("role", "patient")}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新Token失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新Token失败: {str(e)}")


@router.put("/user/role")
async def update_user_role(request: Request, body: UpdateRoleRequest):
    """更新用户角色"""
    mysql = get_mysql()
    if mysql:
        try:
            mysql.execute_update(
                "UPDATE users SET role = :role WHERE id = :id",
                {"id": body.user_id, "role": body.role}
            )
        except Exception as e:
            logger.warning(f"更新用户角色失败: {e}")

    return {"status": "success"}
