"""
项目配置文件
从 .env 文件加载环境变量，提供全局配置
"""

from dotenv import load_dotenv, find_dotenv
import os
from pathlib import Path
import logging.config

# ==================== 加载环境变量 ====================

# 方法 1: 使用 find_dotenv() 自动查找 .env 文件
env_file = find_dotenv()
if env_file:
    print(f"加载 .env 文件: {env_file}")
    load_dotenv(env_file, override=True)
else:
    print("警告: 未找到 .env 文件")
    # 方法 2: 手动指定路径作为备用方案
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        print(f"使用备用路径: {env_path}")
        load_dotenv(env_path, override=True)
    else:
        print(f"错误: .env 文件不存在于 {env_path}")

# 验证关键环境变量是否加载
neo4j_password = os.getenv("NEO4J_PASSWORD")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

if neo4j_password:
    print(f"[OK] NEO4J_PASSWORD loaded (length: {len(neo4j_password)})")
else:
    print("[WARN] NEO4J_PASSWORD not loaded")

if deepseek_api_key:
    print(f"[OK] DEEPSEEK_API_KEY loaded (length: {len(deepseek_api_key)})")
else:
    print("[WARN] DEEPSEEK_API_KEY not loaded")

# ==================== 项目路径配置 ====================

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXAMPLES_DATA_DIR = DATA_DIR / "examples"

# 日志目录
LOG_DIR = BASE_DIR / "logs"

# 创建必要的目录
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, EXAMPLES_DATA_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==================== Neo4j 配置 ====================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# 验证 Neo4j 密码
if not NEO4J_PASSWORD:
    raise ValueError(
        "\n" + "=" * 60 + "\n"
                          "错误: NEO4J_PASSWORD 未配置\n"
                          f"请检查 .env 文件是否存在于: {BASE_DIR}\n"
                          "并确认包含: NEO4J_PASSWORD=your-password\n"
        + "=" * 60
    )

# ==================== MySQL 配置 ====================

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "knowledge_graph")

# 验证 MySQL 密码
if not MYSQL_PASSWORD:
    print("⚠️  警告: MYSQL_PASSWORD 未配置，将使用空密码")

# ==================== DeepSeek API 配置 ====================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))

# 验证 API Key（警告但不报错，因为某些操作可能不需要 LLM）
if not DEEPSEEK_API_KEY:
    print("⚠️  警告: DEEPSEEK_API_KEY 未配置，LLM 功能将不可用")

# ==================== Embedding 配置 ====================

# 是否使用本地 Embedding 模型
USE_LOCAL_EMBEDDING = os.getenv("USE_LOCAL_EMBEDDING", "True").lower() == "true"

# 本地 Embedding 模型路径
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

# 为了兼容性，提供 EMBEDDING_MODEL 别名
EMBEDDING_MODEL = LOCAL_EMBEDDING_MODEL

# Embedding 向量维度
# 注意: BAAI/bge-large-zh-v1.5 的维度是 1024
#       sentence-transformers/paraphrase-multilingual-mpnet-base-v2 的维度是 768
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# ==================== RAG 配置 ====================

# 向量检索返回的 Top-K 结果数
VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "5"))

# 图检索的最大深度
MAX_GRAPH_DEPTH = int(os.getenv("MAX_GRAPH_DEPTH", "3"))

# 混合检索权重
VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.5"))
GRAPH_WEIGHT = float(os.getenv("GRAPH_WEIGHT", "0.5"))

# 最小相关性阈值
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.6"))

# ==================== 应用配置 ====================

# 运行环境: development, production
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# 调试模式
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5001"))

# 提供给测试脚本使用的后端地址
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", str(PORT)))

# 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 应用版本
VERSION = os.getenv("VERSION", "1.0.0")

# ==================== CORS 配置 ====================

# 允许的跨域源
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# 允许的 HTTP 方法
CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

# 允许的请求头
CORS_HEADERS = ["*"]

# ==================== 日志配置 ====================

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": LOG_LEVEL,
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed",
            "level": LOG_LEVEL,
            "encoding": "utf-8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed",
            "level": "ERROR",
            "encoding": "utf-8",
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console", "file", "error_file"],
    },
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "watchfiles": {
            "level": "WARNING",
            "handlers": [],
            "propagate": False,
        },
        "watchfiles.main": {
            "level": "WARNING",
            "handlers": [],
            "propagate": False,
        },
    },
}

# 应用日志配置
try:
    logging.config.dictConfig(LOGGING_CONFIG)
except Exception as e:
    print(f"警告: 日志配置失败: {e}")
    logging.basicConfig(level=LOG_LEVEL)

# ==================== 知识图谱配置 ====================

# 实体类型
ENTITY_TYPES = [
    "Disease",  # 疾病
    "Symptom",  # 症状
    "Treatment",  # 治疗方法
    "Medicine",  # 药物
    "Examination",  # 检查
    "Department",  # 科室
    "Complication",  # 并发症
    "RiskFactor",  # 风险因素
]

# 关系类型
RELATION_TYPES = [
    "HAS_SYMPTOM",  # 有症状
    "TREATED_BY",  # 治疗方式
    "USES_MEDICINE",  # 使用药物
    "REQUIRES_EXAM",  # 需要检查
    "BELONGS_TO",  # 归属科室
    "CAUSES",  # 导致
    "LEADS_TO",  # 引发
    "ASSOCIATED_WITH",  # 相关联
    "INCREASES_RISK",  # 增加风险
]


# ==================== 配置验证 ====================

def validate_config():
    """验证配置是否完整"""
    issues = []

    # 检查 Neo4j 配置
    if not NEO4J_PASSWORD:
        issues.append("NEO4J_PASSWORD 未配置")

    # 检查 DeepSeek 配置（仅警告）
    if not DEEPSEEK_API_KEY:
        issues.append("DEEPSEEK_API_KEY 未配置（LLM 功能将不可用）")

    # 检查目录
    for name, path in [
        ("数据目录", DATA_DIR),
        ("日志目录", LOG_DIR),
    ]:
        if not path.exists():
            issues.append(f"{name} 不存在: {path}")

    return issues


# ==================== 配置摘要 ====================

def print_config_summary():
    """打印配置摘要"""
    print("\n" + "=" * 60)
    print(f"🚀 胰腺炎知识图谱RAG系统 v{VERSION}")
    print("=" * 60)
    print(f"🌐 服务地址: http://{HOST}:{PORT}")
    print(f"🗄️  Neo4j: {NEO4J_URI}")
    print(f"🤖 LLM 模型: {DEEPSEEK_MODEL}")
    print(f"📊 向量模型: {'本地模型' if USE_LOCAL_EMBEDDING else '远程API'} - {EMBEDDING_MODEL}")
    print(f"🔍 调试模式: {'开启' if DEBUG else '关闭'}")
    print("=" * 60)

    # 显示配置问题
    issues = validate_config()
    if issues:
        print("\n⚠️  配置问题:")
        for issue in issues:
            print(f"  ❌ {issue}")
        print()


# ==================== 环境检查 ====================

if __name__ == "__main__":
    """直接运行此文件时，显示配置信息"""
    print_config_summary()

    # 详细配置信息
    print("\n详细配置:")
    print(f"  BASE_DIR: {BASE_DIR}")
    print(f"  DATA_DIR: {DATA_DIR}")
    print(f"  LOG_DIR: {LOG_DIR}")
    print(f"  ENVIRONMENT: {ENVIRONMENT}")
    print(f"  LOG_LEVEL: {LOG_LEVEL}")
    print(f"  EMBEDDING_DIM: {EMBEDDING_DIM}")
    print(f"  VECTOR_TOP_K: {VECTOR_TOP_K}")
    print(f"  MAX_GRAPH_DEPTH: {MAX_GRAPH_DEPTH}")
