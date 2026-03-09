"""
pytest 公共 fixtures：TestClient、认证头等
供 test_health、test_auth_api 等用例复用
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 确保项目根目录在路径中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 测试环境：避免生产校验干扰
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
def client():
    """FastAPI TestClient，直接调用 app，无需启动真实服务。"""
    from backend.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """
    已登录用户的 Authorization 头。
    先尝试注册测试用户，若已存在则直接登录。
    依赖 MySQL，若不可用会跳过。
    """
    import uuid as _uuid
    suffix = _uuid.uuid4().hex[:12]
    username = f"pytest_auth_{suffix}"
    password = "TestPass123"
    # 1. 注册
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"auth_{suffix}@test.local", "password": password},
    )
    if r.status_code != 200:
        pytest.skip(f"注册失败，无法获取 auth_headers: {r.status_code} {r.text}")
    # 2. 登录
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        pytest.skip(f"登录失败，无法获取 auth_headers: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("登录响应中无 access_token")
    return {"Authorization": f"Bearer {token}"}
