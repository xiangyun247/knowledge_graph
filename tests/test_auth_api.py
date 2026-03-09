"""
认证接口 pytest 用例：注册、登录、刷新 Token
依赖 MySQL，若不可用会跳过或失败。
"""
import uuid

import pytest


def test_register_success(client):
    """注册新用户应返回 200 及用户信息"""
    suffix = uuid.uuid4().hex[:12]
    username = f"pytest_reg_{suffix}"
    email = f"reg_{suffix}@test.local"
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "TestPass123"},
    )
    if r.status_code == 500 and "MySQL" in (r.json().get("detail") or ""):
        pytest.skip("MySQL 不可用，跳过注册测试")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    assert "data" in data
    assert data["data"].get("username") == username


def test_register_duplicate_username(client):
    """重复用户名注册应返回 400"""
    suffix = uuid.uuid4().hex[:12]
    username = f"pytest_dup_{suffix}"
    email = f"dup_{suffix}@test.local"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "TestPass123"},
    )
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"dup2_{suffix}@test.local", "password": "TestPass123"},
    )
    if r.status_code == 500 and "MySQL" in (r.json().get("detail") or ""):
        pytest.skip("MySQL 不可用，跳过注册测试")
    assert r.status_code == 400
    assert "已存在" in (r.json().get("detail") or "")


def test_login_success(client):
    """正确用户名密码登录应返回 access_token"""
    suffix = uuid.uuid4().hex[:12]
    username = f"pytest_login_{suffix}"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"login_{suffix}@test.local", "password": "TestPass123"},
    )
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": "TestPass123"},
    )
    if r.status_code == 500 and "MySQL" in (r.json().get("detail") or ""):
        pytest.skip("MySQL 不可用，跳过登录测试")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data.get("token_type") == "Bearer"


def test_login_wrong_password(client):
    """错误密码登录应返回 400"""
    suffix = uuid.uuid4().hex[:12]
    username = f"pytest_wrong_{suffix}"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"wrong_{suffix}@test.local", "password": "TestPass123"},
    )
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": "WrongPassword"},
    )
    if r.status_code == 500 and "MySQL" in (r.json().get("detail") or ""):
        pytest.skip("MySQL 不可用，跳过登录测试")
    assert r.status_code == 400


def test_refresh_valid_token(client):
    """有效 refresh_token 应换取新的 access_token"""
    suffix = uuid.uuid4().hex[:12]
    username = f"pytest_refresh_{suffix}"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"refresh_{suffix}@test.local", "password": "TestPass123"},
    )
    r = client.post("/api/auth/login", json={"username": username, "password": "TestPass123"})
    if r.status_code != 200:
        pytest.skip("登录失败，无法测试 refresh")
    refresh_token = r.json().get("refresh_token")
    if not refresh_token:
        pytest.skip("无 refresh_token")
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_invalid_token(client):
    """无效 refresh_token 应返回 401"""
    r = client.post("/api/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert r.status_code == 401
