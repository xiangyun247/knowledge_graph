"""
健康检查接口 pytest 用例
"""
import pytest


def test_health_returns_200(client):
    """GET /api/health 应返回 200"""
    r = client.get("/api/health")
    assert r.status_code == 200


def test_health_has_status_and_components(client):
    """健康检查响应应包含 status 与 components"""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "components" in data
    assert isinstance(data["components"], dict)


def test_health_components_structure(client):
    """components 中应包含 mysql、neo4j 等组件状态"""
    r = client.get("/api/health")
    assert r.status_code == 200
    comp = r.json().get("components", {})
    # 至少应有这些组件的检查结果
    for key in ("mysql", "neo4j"):
        assert key in comp
        assert "status" in comp[key]
