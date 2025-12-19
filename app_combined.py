"""
统一聚合应用入口

将 RAG 查询服务（api.main.app）和 业务 API（backend.app.app）合并到一个 FastAPI 实例中，
这样前端可以同时访问：
- /api/query、/api/stats 等 RAG 接口
- /api/upload、/api/kg/build 等业务接口
"""

from fastapi import FastAPI

from api.main import app as rag_app  # 含 /api/query 等接口，带完整 lifespan 初始化
from backend.app import app as backend_app  # 含上传、构建图谱等接口

# 直接使用 RAG 应用作为主应用，保留其 lifespan / 中间件 / 文档等配置
app: FastAPI = rag_app

# 将 backend.app 中的所有路由追加到主应用中
for route in backend_app.routes:
    app.router.routes.append(route)


