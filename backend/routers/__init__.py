# routers package - 统一路由注册
from .home import router as home_router
from .history import router as history_router
from .kg import router as kg_router
from .graph import router as graph_router
from .auth import router as auth_router
from .cognitive import router as cognitive_router
from .kb import router as kb_router
from .search import router as search_router
from .templates import router as templates_router

__all__ = [
    "home_router",
    "history_router",
    "kg_router",
    "graph_router",
    "auth_router",
    "cognitive_router",
    "kb_router",
    "search_router",
    "templates_router",
]
