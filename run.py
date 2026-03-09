"""
胰腺炎知识图谱RAG系统 - 应用启动入口
使用 uvicorn 启动 FastAPI 应用
"""

import os
import sys
import warnings
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 关闭 ChromaDB 遥测，避免 posthog 报错刷屏
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
# 抑制 requests 与 urllib3/chardet 版本不匹配的警告
try:
    from requests import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except Exception:
    warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match.*")

import uvicorn
import config
import logging

# 配置日志
logging.config.dictConfig(config.LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# 降低 ChromaDB 遥测相关日志级别，避免 capture() 报错刷屏
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)


def check_dependencies():
    """检查依赖是否满足"""
    issues = []

    # 检查配置
    config_issues = config.validate_config()
    if config_issues:
        issues.extend(config_issues)

    # 检查关键模块
    try:
        from db.neo4j_client import Neo4jClient
        from llm.client import LLMClient, EmbeddingClient
    except ImportError as e:
        issues.append(f"模块导入失败: {e}")

    return issues


def start_server():
    """启动服务器"""
    logger.info("\n" + "=" * 60)
    logger.info("正在启动胰腺炎知识图谱RAG系统...")
    logger.info("=" * 60)

    # 显示配置摘要
    config.print_config_summary()

    # 检查依赖
    issues = check_dependencies()
    if issues:
        logger.error("\n⚠️  启动前检查发现问题:")
        for issue in issues:
            logger.error(f"  ❌ {issue}")
        logger.error("\n请解决上述问题后再启动服务\n")
        sys.exit(1)

    logger.info("\n✓ 依赖检查通过")

    # Agent（Chat）可用性：失败仅告警，不阻塞启动
    try:
        from backend.agent import run_agent
        logger.info("✓ Agent 模块加载成功（Chat 可用）")
    except Exception as e:
        logger.warning("⚠ Agent 模块加载失败，/api/agent/query 与 /api/agent/query/stream 将返回 503: %s", e)
        logger.warning("  请检查: pip install langgraph langchain-openai langchain-core；.env 中 DEEPSEEK_API_KEY")

    # Chroma（文档知识库）可用性：失败仅告警，不阻塞启动
    try:
        from backend.chroma_store import ChromaStore
        _s = ChromaStore()
        _ = _s._collection.count()
        logger.info("✓ Chroma 模块加载成功（文档知识库可用）")
    except Exception as e:
        err = str(e)
        logger.warning("⚠ Chroma 模块加载失败，/api/kb/documents/* 将返回 500: %s", e)
        if "np.float_" in err or "NumPy 2.0" in err:
            logger.warning("  请执行: pip install 'numpy<2'   # Chroma 0.4.x 与 NumPy 2 不兼容")
        else:
            logger.warning("  请检查: pip install chromadb 'numpy<2'；若为 Embedding 失败可再检查 sentence-transformers")

    logger.info(f"\n🚀 正在启动服务器...")
    logger.info(f"   地址: http://{config.HOST}:{config.PORT}")
    logger.info(f"   环境: {config.ENVIRONMENT}")
    logger.info(f"   调试模式: {'开启' if config.DEBUG else '关闭'}")
    logger.info(f"   日志级别: {config.LOG_LEVEL}")

    # 确定应用路径
    # 优先使用聚合应用，将 RAG 查询接口与业务接口统一到一个 FastAPI 实例中
    if (project_root / "app_combined.py").exists():
        app_path = "app_combined:app"
    # 其次回退到原有逻辑
    elif (project_root / "backend" / "app.py").exists():
        app_path = "backend.app:app"
    elif (project_root / "api" / "main.py").exists():
        app_path = "api.main:app"
    else:
        logger.error("❌ 找不到 FastAPI 应用文件")
        logger.error("   请确保存在以下文件之一:")
        logger.error("   - app_combined.py")
        logger.error("   - backend/app.py")
        logger.error("   - api/main.py")
        sys.exit(1)

    logger.info(f"   应用路径: {app_path}\n")

    try:
        # 启动 uvicorn 服务器
        uvicorn.run(
            app_path,
            host=config.HOST,
            port=config.PORT,
            reload=config.DEBUG,  # 开发模式下自动重载
            reload_excludes=["logs/*", "data/*", ".git/*", "*.log", "*.pyc"],  # 排除不需要监控的目录和文件
            log_level=config.LOG_LEVEL.lower(),
            access_log=True,
            # 生产环境配置
            workers=1 if config.DEBUG else 4,  # 生产环境使用多进程
            # SSL 配置（如果需要）
            # ssl_keyfile="path/to/key.pem",
            # ssl_certfile="path/to/cert.pem",
        )
    except KeyboardInterrupt:
        logger.info("\n\n⏹️  服务器已停止")
    except Exception as e:
        logger.error(f"\n❌ 服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    start_server()
