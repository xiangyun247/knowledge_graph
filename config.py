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

# 文档知识库 Chroma 持久化目录（默认 DATA_DIR/chroma，可用 CHROMA_PERSIST_DIR 覆盖）
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "")

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
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "knowledge_graph_system")

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

# ==================== 智谱 GLM-Image 配置 ====================

# 图生模型 API Key（用于 GLM-Image 文生图）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
if not ZHIPU_API_KEY:
    print("⚠️  警告: ZHIPU_API_KEY 未配置，患者教育配图功能将不可用")

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

# Hybrid RAG：RRF（Reciprocal Rank Fusion）常数，常用 60
HYBRID_RAG_RRF_K = int(os.getenv("HYBRID_RAG_RRF_K", "60"))

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
# 参考：表2 实体描述框架、表3 实体关系描述框架

# 实体类型（表2 实体描述框架）
ENTITY_TYPES = [
    # 基础分类
    "Disease",  # 疾病
    "Symptom",  # 症状或体征
    "Population",  # 群体
    "Medicine",  # 药物
    "Prognosis",  # 预后
    # 检查检验及其子分类
    "PhysicalExamination",  # 体格检查
    "LaboratoryExamination",  # 实验室检查
    "ImagingExamination",  # 影像学检查
    "PathologyExamination",  # 病理检查
    "OtherExamination",  # 其它检查
    "AbnormalExaminationResult",  # 异常检查结果
    # 治疗及其子分类
    "TCMTreatment",  # 中医治疗
    "Surgery",  # 手术
    "DrugTreatment",  # 药物治疗
    "WesternPhysicalTherapy",  # 西医理疗
    "OtherTreatment",  # 其它治疗
    # 解剖部位及物质
    "AnatomicalSite",  # 解剖部位
    "AnatomicalSubstance",  # 解剖物质
    # 医用设备、器械和材料
    "MedicalEquipment",  # 医用设备、器械和材料
    # 机构
    "Hospital",  # 医院
    "Department",  # 科室
    # 病因类及其子分类
    "Gene",  # 基因
    "Microorganism",  # 微生物类
    "PhysicalChemicalFactor",  # 理化因素
    "PsychologicalBehavior",  # 心理行为
    "Lifestyle",  # 生活习惯
    "ImmuneFactor",  # 免疫因素
    "DisuseFactor",  # 废用性因素
    # 语义
    "ICD10Code",  # ICD10 编码
    "Synonym",  # 同义词
]

# 关系类型（表3 实体关系描述框架）
RELATION_TYPES = [
    # 疾病-异常检查结果 / 检查检验-异常检查结果
    "HAS_ABNORMAL_EXAM_RESULT",  # 疾病-异常检查结果
    "EXAM_HAS_ABNORMAL_RESULT",  # 检查检验-异常检查结果
    # 疾病-检查检验
    "REQUIRES_EXAM",  # 用于检查
    # 疾病/症状-治疗/药物
    "TREATED_BY",  # 用于治疗
    "PREVENTED_BY",  # 用于预防
    # 治疗-疾病
    "TREATS_COMPLICATION",  # 治疗并发症
    # 药物-疾病/症状
    "HAS_SIDE_EFFECT",  # 副作用
    # 疾病-症状或体征
    "HAS_SYMPTOM",  # 症状或体征
    # 疾病-群体
    "AFFECTS_POPULATION",  # 多发人群
    # 疾病-疾病
    "HAS_COMPLICATION",  # 并发症
    "DIFFERENTIAL_DIAGNOSIS",  # 鉴别诊断
    # 疾病-病因类
    "HAS_ETIOLOGY",  # 病因
    # 疾病-机构
    "BELONGS_TO_DEPARTMENT",  # 就诊科室
    "TREATED_AT_HOSPITAL",  # 就诊医院
    # 疾病-解剖部位及物质
    "AFFECTS_SITE",  # 发病部位
    # 疾病-预后
    "HAS_PROGNOSIS",  # 预后
    # 检查检验/治疗-医疗设备
    "USES_EQUIPMENT",  # 使用于
    # 通用
    "BELONGS_TO",  # 属于（任意实体-任意实体）
    # 语义
    "HAS_ICD10_CODE",  # ICD10 编码
    "HAS_SYNONYM",  # 别称
]

# ==================== 中文↔英文映射表 ====================
# 用于 LLM 返回中文类型时的规范化、前端展示、查询解析等

# 实体类型：中文 → 英文
ENTITY_TYPE_ZH_TO_EN = {
    # 基础
    "疾病": "Disease",
    "症状或体征": "Symptom",
    "症状": "Symptom",
    "体征": "Symptom",
    "群体": "Population",
    "药物": "Medicine",
    "预后": "Prognosis",
    # 检查检验
    "体格检查": "PhysicalExamination",
    "实验室检查": "LaboratoryExamination",
    "影像学检查": "ImagingExamination",
    "病理检查": "PathologyExamination",
    "其它检查": "OtherExamination",
    "其他检查": "OtherExamination",
    "异常检查结果": "AbnormalExaminationResult",
    # 治疗
    "中医治疗": "TCMTreatment",
    "手术": "Surgery",
    "药物治疗": "DrugTreatment",
    "西医理疗": "WesternPhysicalTherapy",
    "其它治疗": "OtherTreatment",
    "其他治疗": "OtherTreatment",
    # 解剖
    "解剖部位": "AnatomicalSite",
    "解剖物质": "AnatomicalSubstance",
    # 设备
    "医用设备": "MedicalEquipment",
    "器械": "MedicalEquipment",
    "医用设备、器械和材料": "MedicalEquipment",
    # 机构
    "医院": "Hospital",
    "科室": "Department",
    # 病因类
    "基因": "Gene",
    "微生物类": "Microorganism",
    "微生物": "Microorganism",
    "理化因素": "PhysicalChemicalFactor",
    "心理行为": "PsychologicalBehavior",
    "生活习惯": "Lifestyle",
    "免疫因素": "ImmuneFactor",
    "废用性因素": "DisuseFactor",
    # 语义
    "ICD10编码": "ICD10Code",
    "ICD10 编码": "ICD10Code",
    "同义词": "Synonym",
    "别称": "Synonym",
}

# 实体类型：英文 → 中文（用于前端展示、日志等）
ENTITY_TYPE_EN_TO_ZH = {
    "Disease": "疾病",
    "Symptom": "症状或体征",
    "Population": "群体",
    "Medicine": "药物",
    "Prognosis": "预后",
    "PhysicalExamination": "体格检查",
    "LaboratoryExamination": "实验室检查",
    "ImagingExamination": "影像学检查",
    "PathologyExamination": "病理检查",
    "OtherExamination": "其它检查",
    "AbnormalExaminationResult": "异常检查结果",
    "TCMTreatment": "中医治疗",
    "Surgery": "手术",
    "DrugTreatment": "药物治疗",
    "WesternPhysicalTherapy": "西医理疗",
    "OtherTreatment": "其它治疗",
    "AnatomicalSite": "解剖部位",
    "AnatomicalSubstance": "解剖物质",
    "MedicalEquipment": "医用设备、器械和材料",
    "Hospital": "医院",
    "Department": "科室",
    "Gene": "基因",
    "Microorganism": "微生物类",
    "PhysicalChemicalFactor": "理化因素",
    "PsychologicalBehavior": "心理行为",
    "Lifestyle": "生活习惯",
    "ImmuneFactor": "免疫因素",
    "DisuseFactor": "废用性因素",
    "ICD10Code": "ICD10编码",
    "Synonym": "同义词",
}

# 关系类型：中文 → 英文
RELATION_TYPE_ZH_TO_EN = {
    "异常检查结果": "HAS_ABNORMAL_EXAM_RESULT",  # 疾病-异常检查结果
    "用于检查": "REQUIRES_EXAM",
    "用于治疗": "TREATED_BY",
    "用于预防": "PREVENTED_BY",
    "治疗并发症": "TREATS_COMPLICATION",
    "副作用": "HAS_SIDE_EFFECT",
    "症状或体征": "HAS_SYMPTOM",
    "多发人群": "AFFECTS_POPULATION",
    "并发症": "HAS_COMPLICATION",
    "鉴别诊断": "DIFFERENTIAL_DIAGNOSIS",
    "病因": "HAS_ETIOLOGY",
    "就诊科室": "BELONGS_TO_DEPARTMENT",
    "就诊医院": "TREATED_AT_HOSPITAL",
    "发病部位": "AFFECTS_SITE",
    "预后": "HAS_PROGNOSIS",
    "使用于": "USES_EQUIPMENT",
    "属于": "BELONGS_TO",
    "ICD10编码": "HAS_ICD10_CODE",
    "ICD10 编码": "HAS_ICD10_CODE",
    "别称": "HAS_SYNONYM",
}

# 关系类型：英文 → 中文
RELATION_TYPE_EN_TO_ZH = {
    "HAS_ABNORMAL_EXAM_RESULT": "异常检查结果",
    "EXAM_HAS_ABNORMAL_RESULT": "检查-异常结果",
    "REQUIRES_EXAM": "用于检查",
    "TREATED_BY": "用于治疗",
    "PREVENTED_BY": "用于预防",
    "TREATS_COMPLICATION": "治疗并发症",
    "HAS_SIDE_EFFECT": "副作用",
    "HAS_SYMPTOM": "症状或体征",
    "AFFECTS_POPULATION": "多发人群",
    "HAS_COMPLICATION": "并发症",
    "DIFFERENTIAL_DIAGNOSIS": "鉴别诊断",
    "HAS_ETIOLOGY": "病因",
    "BELONGS_TO_DEPARTMENT": "就诊科室",
    "TREATED_AT_HOSPITAL": "就诊医院",
    "AFFECTS_SITE": "发病部位",
    "HAS_PROGNOSIS": "预后",
    "USES_EQUIPMENT": "使用于",
    "BELONGS_TO": "属于",
    "HAS_ICD10_CODE": "ICD10编码",
    "HAS_SYNONYM": "别称",
}


def resolve_entity_type(value: str) -> str:
    """
    将实体类型（中文或英文）解析为英文类型。
    若已是英文且在 ENTITY_TYPES 中，直接返回；若为中文则查表映射；否则返回默认 Disease。
    """
    if not value or not isinstance(value, str):
        return "Disease"
    v = value.strip()
    if v in ENTITY_TYPES:
        return v
    return ENTITY_TYPE_ZH_TO_EN.get(v, "Disease")


def resolve_relation_type(value: str) -> str:
    """
    将关系类型（中文或英文）解析为英文类型。
    若已是英文且在 RELATION_TYPES 中，直接返回；若为中文则查表映射；否则返回默认 BELONGS_TO。
    """
    if not value or not isinstance(value, str):
        return "BELONGS_TO"
    v = value.strip()
    if v in RELATION_TYPES:
        return v
    return RELATION_TYPE_ZH_TO_EN.get(v, "BELONGS_TO")


# ==================== 后处理校验配置 ====================

# 实体名最小有效长度（字符数，中文按 1 字计）
ENTITY_NAME_MIN_LEN = 2

# 实体名黑名单：不应作为独立实体抽取的通用词（负样本提示）
ENTITY_NAME_BLACKLIST = frozenset({
    "患者", "病人", "患者主诉", "主诉", "今日", "一般情况", "可", "良好",
    "正常", "无", "有", "是", "否", "等", "及", "或", "与", "和",
    "该", "此", "其", "本", "上述", "如下", "例如", "如", "若",
})

# 关系语义约束：predicate -> (subject_types, object_types)，空集合表示不校验
# 用于后处理时软校验，不匹配时打日志，不强制丢弃
RELATION_SEMANTICS = {
    "HAS_SYMPTOM": ({"Disease", "Symptom"}, {"Symptom"}),
    "HAS_ABNORMAL_EXAM_RESULT": ({"Disease"}, {"AbnormalExaminationResult"}),
    "EXAM_HAS_ABNORMAL_RESULT": (
        {"PhysicalExamination", "LaboratoryExamination", "ImagingExamination", "PathologyExamination", "OtherExamination"},
        {"AbnormalExaminationResult"},
    ),
    "REQUIRES_EXAM": ({"Disease", "Symptom"}, {"PhysicalExamination", "LaboratoryExamination", "ImagingExamination", "PathologyExamination", "OtherExamination"}),
    "TREATED_BY": ({"Disease", "Symptom"}, {"Medicine", "TCMTreatment", "Surgery", "DrugTreatment", "WesternPhysicalTherapy", "OtherTreatment"}),
    "PREVENTED_BY": ({"Disease", "Symptom"}, {"Medicine", "TCMTreatment", "Surgery", "DrugTreatment", "WesternPhysicalTherapy", "OtherTreatment"}),
    "TREATS_COMPLICATION": ({"TCMTreatment", "Surgery", "DrugTreatment", "WesternPhysicalTherapy", "OtherTreatment"}, {"Disease"}),
    "HAS_SIDE_EFFECT": ({"Medicine"}, {"Disease", "Symptom"}),
    "AFFECTS_POPULATION": ({"Disease"}, {"Population"}),
    "HAS_COMPLICATION": ({"Disease"}, {"Disease"}),
    "DIFFERENTIAL_DIAGNOSIS": ({"Disease"}, {"Disease"}),
    "HAS_ETIOLOGY": ({"Disease"}, {"Gene", "Microorganism", "PhysicalChemicalFactor", "PsychologicalBehavior", "Lifestyle", "ImmuneFactor", "DisuseFactor", "Disease", "Symptom"}),
    "BELONGS_TO_DEPARTMENT": ({"Disease"}, {"Department"}),
    "TREATED_AT_HOSPITAL": ({"Disease"}, {"Hospital"}),
    "AFFECTS_SITE": ({"Disease"}, {"AnatomicalSite", "AnatomicalSubstance"}),
    "HAS_PROGNOSIS": ({"Disease"}, {"Prognosis"}),
    "USES_EQUIPMENT": (
        {"PhysicalExamination", "LaboratoryExamination", "ImagingExamination", "PathologyExamination", "OtherExamination",
         "TCMTreatment", "Surgery", "DrugTreatment", "WesternPhysicalTherapy", "OtherTreatment"},
        {"MedicalEquipment"},
    ),
}


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
    print(f"🚀 智护银龄·忆路康知识辅助系统 v{VERSION}")
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
