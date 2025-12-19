"""
FastAPI 服务器 - 提供知识图谱查询接口
优化版：增强实体提取 + 改进查询逻辑 + 消除警告
"""
import sys
from pathlib import Path
import re
from typing import List, Dict, Any, Optional
import logging

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ========== 导入项目模块 ==========
from db.neo4j_client import Neo4jClient
from rag.rag_pipeline import RAGPipeline
from rag.graph_retriever import GraphRetriever
from llm.client import LLMClient, EmbeddingClient
import config  # 用 config.DEEPSEEK_xxx 等
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==================== 初始化 FastAPI 应用 ====================
app = FastAPI(
    title="医疗知识图谱 API",
    description="基于 Neo4j 的医疗知识图谱查询系统（优化版）",
    version="2.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
neo4j_client: Optional[Neo4jClient] = None
rag_pipeline: Optional[RAGPipeline] = None


# ==================== Pydantic 模型 ====================

class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., description="用户问题", min_length=1)
    max_results: int = Field(default=5, ge=1, le=20, description="最大返回结果数")


class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    query_type: str = Field(default="unknown", description="查询类型")

class ImportEntity(BaseModel):
    """导入用的实体定义"""
    name: str = Field(..., description="实体名称")
    type: str = Field(default="Entity", description="实体类型（节点标签）")
    properties: Dict[str, Any] = Field(default_factory=dict, description="实体属性字典")


class ImportRelationship(BaseModel):
    """导入用的关系定义"""
    source: str = Field(..., description="起始实体名称")
    target: str = Field(..., description="目标实体名称")
    type: str = Field(default="RELATED_TO", description="关系类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="关系属性字典")


class ImportRequest(BaseModel):
    """导入请求体"""
    entities: List[ImportEntity] = Field(default_factory=list, description="要导入的实体列表")
    relationships: List[ImportRelationship] = Field(default_factory=list, description="要导入的关系列表")


# ==================== 智能实体提取器 ====================

class EntityExtractor:
    """增强版实体提取器"""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self._load_entities_from_db()

        # 查询意图模式
        self.intent_patterns = {
            "症状查询": r"(什么症状|有.*症状|症状.*是|表现|临床表现)",
            "治疗查询": r"(怎么治疗|如何治疗|治疗.*方法|吃什么药|用什么药|药物治疗)",
            "科室查询": r"(看什么科|挂.*科|什么科室|哪个科|就诊科室)",
            "病因查询": r"(什么疾病|哪些疾病|疾病.*症状|是.*病|可能是)",
            "药物查询": r"(.*药.*作用|.*药.*治疗|.*药.*副作用|.*药.*功效)"
        }

    def _load_entities_from_db(self):
        """从数据库加载所有实体"""
        try:
            with self.neo4j_client.driver.session() as session:
                # 加载疾病
                result = session.run("MATCH (d:Disease) RETURN d.name as name")
                self.diseases = [record["name"] for record in result]

                # 加载症状
                result = session.run("MATCH (s:Symptom) RETURN s.name as name")
                self.symptoms = [record["name"] for record in result]

                # 加载药物
                result = session.run("MATCH (d:Drug) RETURN d.name as name")
                self.drugs = [record["name"] for record in result]

                logger.info(f"✅ 实体加载完成: {len(self.diseases)} 疾病, "
                            f"{len(self.symptoms)} 症状, {len(self.drugs)} 药物")
        except Exception as e:
            logger.error(f"❌ 实体加载失败: {e}")
            self.diseases = []
            self.symptoms = []
            self.drugs = []

    def extract_disease(self, text: str) -> Optional[str]:
        """提取疾病实体（最长匹配）"""
        matched = [d for d in self.diseases if d in text]
        return max(matched, key=len) if matched else None

    def extract_symptom(self, text: str) -> Optional[str]:
        """提取症状实体（最长匹配）"""
        matched = [s for s in self.symptoms if s in text]
        return max(matched, key=len) if matched else None

    def extract_drug(self, text: str) -> Optional[str]:
        """提取药物实体（最长匹配）"""
        matched = [d for d in self.drugs if d in text]
        return max(matched, key=len) if matched else None

    def detect_intent(self, text: str) -> Optional[str]:
        """检测查询意图"""
        for intent, pattern in self.intent_patterns.items():
            if re.search(pattern, text):
                return intent
        return None


# 全局实体提取器（启动后初始化）
entity_extractor: Optional[EntityExtractor] = None


# ==================== 增强查询函数 ====================

def enhanced_query(question: str, max_results: int = 5) -> QueryResponse:
    """
    增强版知识图谱查询
    优先级：实体提取 > RAG Pipeline > 基础查询
    """

    if not entity_extractor:
        return QueryResponse(
            question=question,
            answer="系统初始化中，请稍后重试",
            query_type="error"
        )

    # 1. 提取实体
    disease = entity_extractor.extract_disease(question)
    symptom = entity_extractor.extract_symptom(question)
    drug = entity_extractor.extract_drug(question)

    # 2. 识别意图
    intent = entity_extractor.detect_intent(question)

    logger.info(f"实体提取: disease={disease}, symptom={symptom}, drug={drug}, intent={intent}")

    # ========== 症状查询 ==========
    if intent == "症状查询" and disease:
        return query_disease_symptoms(disease, question)

    # ========== 治疗查询 ==========
    elif intent == "治疗查询" and disease:
        return query_disease_treatment(disease, question)

    # ========== 科室查询 ==========
    elif intent == "科室查询" and disease:
        return query_disease_department(disease, question)

    # ========== 病因查询 ==========
    elif intent == "病因查询" and symptom:
        return query_symptom_diseases(symptom, question)

    # ========== 药物查询 ==========
    elif intent == "药物查询" and drug:
        return query_drug_info(drug, question)

    # ========== 降级到 RAG Pipeline ==========
    # ========== 降级到 RAG Pipeline ==========
    if rag_pipeline:
        try:
            # 与 test_system.py 的用法保持一致：优先依赖图检索，关闭向量检索
            # pipeline.answer(query, use_graph=True, use_vector=False)
            result = rag_pipeline.answer(
                question,
                use_graph=True,
                use_vector=False,
            )
            return QueryResponse(
                question=question,
                answer=result.get("answer", "") or "抱歉，未能生成有效回答",
                sources=result.get("sources", []),
                query_type="rag"
            )
        except Exception as e:
            logger.error(f"RAG 查询失败: {e}")

    # ========== 最终降级到基础查询 ==========
    return process_basic_query(question)


# ==================== 专用查询函数 ====================

def query_disease_symptoms(disease: str, question: str) -> QueryResponse:
    """查询疾病症状"""
    try:
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (d:Disease {name: $disease})-[:HAS_SYMPTOM]->(s:Symptom)
                RETURN d.name as disease, collect(s.name) as symptoms
                LIMIT 1
            """, disease=disease)

            record = result.single()
            if record and record["symptoms"]:
                symptoms = record["symptoms"]
                return QueryResponse(
                    question=question,
                    answer=f"**{disease}** 的主要症状包括：\n\n" +
                           "\n".join(f"• {s}" for s in symptoms),
                    sources=[{"type": "Disease", "name": disease}],
                    query_type="symptom"
                )
    except Exception as e:
        logger.error(f"症状查询失败: {e}")

    return QueryResponse(
        question=question,
        answer=f"抱歉，未找到 **{disease}** 的症状信息",
        query_type="symptom"
    )


def query_disease_treatment(disease: str, question: str) -> QueryResponse:
    """查询疾病治疗"""
    try:
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (d:Disease {name: $disease})<-[:TREATS]-(drug:Drug)
                RETURN d.name as disease, collect(drug.name) as drugs
                LIMIT 1
            """, disease=disease)

            record = result.single()
            if record and record["drugs"]:
                drugs = record["drugs"]
                return QueryResponse(
                    question=question,
                    answer=f"**{disease}** 的治疗药物包括：\n\n" +
                           "\n".join(f"• {d}" for d in drugs) +
                           "\n\n⚠️ 请在医生指导下使用药物",
                    sources=[{"type": "Disease", "name": disease}],
                    query_type="treatment"
                )
    except Exception as e:
        logger.error(f"治疗查询失败: {e}")

    return QueryResponse(
        question=question,
        answer=f"抱歉，未找到 **{disease}** 的治疗信息",
        query_type="treatment"
    )


def query_disease_department(disease: str, question: str) -> QueryResponse:
    """查询就诊科室"""
    try:
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (d:Disease {name: $disease})-[:BELONGS_TO]->(dept:Department)
                RETURN d.name as disease, dept.name as department
                LIMIT 1
            """, disease=disease)

            record = result.single()
            if record:
                department = record["department"]
                return QueryResponse(
                    question=question,
                    answer=f"**{disease}** 建议就诊科室：**{department}**",
                    sources=[{"type": "Disease", "name": disease}],
                    query_type="department"
                )
    except Exception as e:
        logger.error(f"科室查询失败: {e}")

    return QueryResponse(
        question=question,
        answer=f"抱歉，未找到 **{disease}** 的科室信息",
        query_type="department"
    )


def query_symptom_diseases(symptom: str, question: str) -> QueryResponse:
    """根据症状查询可能的疾病"""
    try:
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom {name: $symptom})
                RETURN collect(d.name) as diseases
                LIMIT 1
            """, symptom=symptom)

            record = result.single()
            if record and record["diseases"]:
                diseases = record["diseases"]
                return QueryResponse(
                    question=question,
                    answer=f"出现 **{symptom}** 可能是以下疾病的症状：\n\n" +
                           "\n".join(f"• {d}" for d in diseases) +
                           "\n\n⚠️ 建议及时就医确诊",
                    sources=[{"type": "Symptom", "name": symptom}],
                    query_type="disease_by_symptom"
                )
    except Exception as e:
        logger.error(f"病因查询失败: {e}")

    return QueryResponse(
        question=question,
        answer=f"抱歉，未找到与 **{symptom}** 相关的疾病信息",
        query_type="disease_by_symptom"
    )


def query_drug_info(drug: str, question: str) -> QueryResponse:
    """查询药物信息"""
    try:
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (drug:Drug {name: $drug})-[:TREATS]->(d:Disease)
                RETURN drug.name as drug, collect(d.name) as diseases
                LIMIT 1
            """, drug=drug)

            record = result.single()
            if record and record["diseases"]:
                diseases = record["diseases"]
                return QueryResponse(
                    question=question,
                    answer=f"**{drug}** 主要用于治疗：\n\n" +
                           "\n".join(f"• {d}" for d in diseases) +
                           "\n\n⚠️ 请遵医嘱使用",
                    sources=[{"type": "Drug", "name": drug}],
                    query_type="drug"
                )
    except Exception as e:
        logger.error(f"药物查询失败: {e}")

    return QueryResponse(
        question=question,
        answer=f"抱歉，未找到 **{drug}** 的相关信息",
        query_type="drug"
    )


def process_basic_query(question: str) -> QueryResponse:
    """基础查询处理（最终降级方案）"""
    return QueryResponse(
        question=question,
        answer=f"抱歉，我无法理解您的问题：\"{question}\"\n\n"
               f"💡 **您可以尝试这样提问：**\n\n"
               f"• \"高血压有什么症状？\"\n"
               f"• \"糖尿病怎么治疗？\"\n"
               f"• \"感冒应该看什么科？\"\n"
               f"• \"头痛可能是什么病？\"\n"
               f"• \"二甲双胍有什么作用？\"",
        query_type="fallback"
    )


# ==================== 原有辅助函数（保留） ====================

def get_graph_stats() -> Dict[str, Any]:
    """获取知识图谱统计信息"""
    try:
        with neo4j_client.driver.session() as session:
            entity_stats = {}
            for entity_type in ["Disease", "Symptom", "Drug", "Department"]:
                result = session.run(f"MATCH (n:{entity_type}) RETURN count(n) as count")
                count = result.single()["count"]
                entity_stats[entity_type] = count

            relationship_stats = {}
            for rel_type in ["HAS_SYMPTOM", "TREATS", "BELONGS_TO"]:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                count = result.single()["count"]
                relationship_stats[rel_type] = count

            return {
                "entities": entity_stats,
                "relationships": relationship_stats,
                "total_entities": sum(entity_stats.values()),
                "total_relationships": sum(relationship_stats.values())
            }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise


def search_entities_by_type(entity_type: str, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按类型搜索实体"""
    try:
        query = f"""
        MATCH (n:{entity_type})
        WHERE n.name =~ $regex
        RETURN n
        LIMIT $limit
        """
        regex = f"(?i).*{keyword}.*"

        with neo4j_client.driver.session() as session:
            result = session.run(query, regex=regex, limit=limit)
            return [dict(record["n"]) for record in result]
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return []


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """启动时执行"""
    global neo4j_client, rag_pipeline, entity_extractor

    logger.info("=" * 70)
    logger.info("🚀 API 服务器启动中...")
    logger.info(f"📊 Neo4j: {NEO4J_URI}")

    try:
        # 初始化 Neo4j 客户端
        neo4j_client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        logger.info("✅ 数据库连接成功")

        # 初始化实体提取器
        entity_extractor = EntityExtractor(neo4j_client)
        logger.info("✅ 实体提取器初始化成功")

        # 初始化 LLM 客户端
        try:
            llm_client = LLMClient(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL,
                model=config.DEEPSEEK_MODEL,
            )
            if not llm_client.verify_connection():
                logger.warning("⚠️ LLM 连接测试失败，将在没有 RAG 的情况下运行")
                llm_client = None
        except Exception as e:
            logger.warning(f"⚠️ LLM 客户端初始化失败: {e}")
            llm_client = None

        # 初始化 Embedding 客户端
        try:
            embedding_client = EmbeddingClient()
        except Exception as e:
            logger.warning(f"⚠️ Embedding 客户端初始化失败: {e}")
            embedding_client = None

        # 初始化 RAG Pipeline（仅在依赖都就绪时）
        if llm_client and embedding_client:
            try:
                rag_pipeline = RAGPipeline(
                    neo4j_client=neo4j_client,
                    llm_client=llm_client,
                    embedding_client=embedding_client,
                )
                logger.info("✅ RAG Pipeline 初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ RAG Pipeline 初始化失败: {e}")
                rag_pipeline = None
        else:
            rag_pipeline = None
            logger.info("ℹ️ RAG Pipeline 未启用（LLM 或 Embedding 不可用）")


    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        raise

    logger.info("✅ API 服务器已启动")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时执行"""
    logger.info("🛑 API 服务器关闭中...")
    if neo4j_client:
        neo4j_client.close()
        logger.info("✅ 数据库连接已关闭")


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗知识图谱 API 服务（优化版）",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running",
        "features": {
            "entity_extraction": entity_extractor is not None,
            "rag_enabled": rag_pipeline is not None
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        with neo4j_client.driver.session() as session:
            session.run("RETURN 1")
        return {
            "status": "healthy",
            "database": "connected",
            "entity_extractor": entity_extractor is not None,
            "rag_enabled": rag_pipeline is not None
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.get("/stats")
async def get_stats_endpoint():
    """获取知识图谱统计信息"""
    try:
        return get_graph_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_endpoint(
        entity_type: str = Query(..., description="实体类型（Disease, Symptom, Drug, Department）"),
        keyword: str = Query(..., description="搜索关键词"),
        limit: int = Query(10, ge=1, le=100, description="返回结果数量限制")
):
    """搜索实体"""
    try:
        results = search_entities_by_type(entity_type, keyword, limit)
        logger.info(f"搜索结果: 找到 {len(results)} 条记录")
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    知识图谱查询接口（优化版）

    查询优先级：
    1. 实体提取 + 意图识别
    2. RAG Pipeline（如果可用）
    3. 基础查询降级
    """
    try:
        logger.info(f"收到查询: {request.question}")
        response = enhanced_query(request.question, request.max_results)
        logger.info(f"查询完成: type={response.query_type}")
        return response
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import")
async def import_data_endpoint(request: ImportRequest):
    """
    简单的图数据导入接口

    请求格式参考 import_data.py:
    - entities: [{name, type, properties}]
    - relationships: [{source, target, type, properties}]
    """
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="数据库未初始化")

    # label / 关系类型简单过滤，只允许字母数字下划线
    def _sanitize_label(name: str, default: str) -> str:
        import re
        if not name:
            return default
        if re.fullmatch(r"[A-Za-z0-9_]+", name):
            return name
        logger.warning(f"非法标签名/关系名被重写: {name} -> {default}")
        return default

    stats = {
        "entities_created": 0,
        "relationships_created": 0
    }

    try:
        with neo4j_client.driver.session() as session:
            # 导入实体
            for entity in request.entities:
                label = _sanitize_label(entity.type, "Entity")
                cypher = f"""
                MERGE (n:{label} {{name: $name}})
                SET n += $props
                RETURN id(n) as id
                """
                session.run(
                    cypher,
                    name=entity.name,
                    props=entity.properties or {}
                )
                stats["entities_created"] += 1

            # 导入关系
            for rel in request.relationships:
                rel_type = _sanitize_label(rel.type, "RELATED_TO")
                cypher = f"""
                MATCH (a {{name: $source}}), (b {{name: $target}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $props
                RETURN id(r) as id
                """
                session.run(
                    cypher,
                    source=rel.source,
                    target=rel.target,
                    props=rel.properties or {}
                )
                stats["relationships_created"] += 1

    except Exception as e:
        logger.error(f"导入数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {e}")

    logger.info(
        f"导入完成: 实体 {stats['entities_created']} 个, "
        f"关系 {stats['relationships_created']} 个"
    )
    return {
        "status": "success",
        "message": "数据导入完成",
        "stats": stats
    }

# ==================== 主程序 ====================

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 70)
    logger.info("🏥 医疗知识图谱 API 服务器（优化版）")
    logger.info("=" * 70)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5001,
        log_level="info"
    )
