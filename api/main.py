"""
胰腺炎知识图谱RAG系统 - FastAPI 应用主文件
提供 RESTful API 接口
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import logging
import config
from contextlib import asynccontextmanager

# 导入核心模块
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient
from rag.rag_pipeline import RAGPipeline
from rag.graph_retriever import GraphRetriever

logger = logging.getLogger(__name__)

# ==================== 全局变量 ====================

# 全局客户端实例
neo4j_client: Optional[Neo4jClient] = None
llm_client: Optional[LLMClient] = None
embedding_client: Optional[EmbeddingClient] = None
rag_pipeline: Optional[RAGPipeline] = None
graph_retriever: Optional[GraphRetriever] = None


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("=" * 60)
    logger.info("正在初始化应用...")
    logger.info("=" * 60)

    global neo4j_client, llm_client, embedding_client, rag_pipeline, graph_retriever

    try:
        # 初始化 Neo4j 客户端
        logger.info("正在连接 Neo4j...")
        neo4j_client = Neo4jClient()
        if not neo4j_client.verify_connection():
            raise Exception("Neo4j 连接失败")
        logger.info("✓ Neo4j 连接成功")

        # 初始化 LLM 客户端
        logger.info("正在连接 LLM 服务...")
        llm_client = LLMClient()
        if not llm_client.verify_connection():
            raise Exception("LLM 连接失败")
        logger.info("✓ LLM 连接成功")

        # 初始化 Embedding 客户端
        logger.info("正在加载 Embedding 模型...")
        embedding_client = EmbeddingClient()
        logger.info("✓ Embedding 模型加载成功")

        # 初始化 RAG 流水线
        logger.info("正在初始化 RAG 流水线...")
        rag_pipeline = RAGPipeline(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )
        logger.info("✓ RAG 流水线初始化成功")

        # 初始化图谱检索器
        logger.info("正在初始化图谱检索器...")
        graph_retriever = GraphRetriever(neo4j_client=neo4j_client)
        logger.info("✓ 图谱检索器初始化成功")

        logger.info("=" * 60)
        logger.info("✅ 应用初始化完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 应用初始化失败: {e}")
        raise

    yield  # 应用运行中

    # 关闭时执行
    logger.info("正在关闭应用...")

    if neo4j_client:
        neo4j_client.close()
        logger.info("✓ Neo4j 连接已关闭")

    if llm_client:
        llm_client.close()
        logger.info("✓ LLM 客户端已关闭")

    logger.info("✅ 应用已关闭")


# ==================== 创建应用 ====================

app = FastAPI(
    title="胰腺炎知识图谱RAG系统",
    description="基于知识图谱的医学问答系统",
    version=config.VERSION,
    debug=config.DEBUG,
    lifespan=lifespan
)

# ==================== CORS 中间件 ====================

# 使用硬编码的CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ==================== 请求/响应模型 ====================

class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., description="用户问题", min_length=1, max_length=500)
    use_graph: bool = Field(True, description="是否使用图检索")
    use_vector: bool = Field(True, description="是否使用向量检索")
    top_k: int = Field(5, description="返回结果数量", ge=1, le=20)

    class Config:
        json_schema_extra = {
            "example": {
                "question": "什么是重症急性胰腺炎？",
                "use_graph": True,
                "use_vector": True,
                "top_k": 5
            }
        }


class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str = Field(..., description="原始问题")
    answer: str = Field(..., description="生成的答案")
    # 只允许能被 JSON 序列化的基础类型，避免 neo4j.time.DateTime 之类的对象导致序列化报错
    sources: List[Dict[str, Union[str, int, float, bool, None, List[Any], Dict[str, Any]]]] = Field(
        default_factory=list,
        description="信息来源"
    )
    confidence: float = Field(0.0, description="置信度", ge=0.0, le=1.0)
    processing_time: float = Field(..., description="处理时间（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "什么是重症急性胰腺炎？",
                "answer": "重症急性胰腺炎（SAP）是急性胰腺炎的严重类型...",
                "sources": [
                    {"type": "Disease", "name": "重症急性胰腺炎", "relevance": 0.95}
                ],
                "confidence": 0.9,
                "processing_time": 1.23
            }
        }


class GraphDataResponse(BaseModel):
    """图谱数据响应模型"""
    nodes: List[dict]
    edges: List[dict]


class EntityRequest(BaseModel):
    """实体创建请求"""
    name: str = Field(..., description="实体名称")
    type: str = Field(..., description="实体类型")
    description: Optional[str] = Field(None, description="实体描述")


class RelationRequest(BaseModel):
    """关系创建请求"""
    subject: str = Field(..., description="主体实体名称")
    predicate: str = Field(..., description="关系类型")
    object: str = Field(..., description="客体实体名称")


class KnowledgeImportRequest(BaseModel):
    """知识导入请求"""
    text: str = Field(..., description="知识文本", min_length=10)
    source: Optional[str] = Field(None, description="来源")


# ==================== 依赖注入 ====================

def get_rag_pipeline() -> RAGPipeline:
    """获取 RAG 流水线实例"""
    if rag_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG 流水线未初始化，请稍后再试"
        )
    return rag_pipeline


def get_neo4j_client() -> Neo4jClient:
    """获取 Neo4j 客户端实例"""
    if neo4j_client is None:
        raise HTTPException(
            status_code=503,
            detail="数据库连接未建立，请稍后再试"
        )
    return neo4j_client


# ==================== 路由 ====================

@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "name": "胰腺炎知识图谱RAG系统",
        "version": config.VERSION,
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "query": "/api/query",
            "stats": "/api/stats"
        }
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    health_status = {
        "status": "healthy",
        "version": config.VERSION,
        "environment": config.ENVIRONMENT,
        "components": {}
    }

    # 检查 Neo4j
    try:
        if neo4j_client and neo4j_client.verify_connection():
            health_status["components"]["neo4j"] = "healthy"
        else:
            health_status["components"]["neo4j"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception:
        health_status["components"]["neo4j"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查 LLM
    try:
        if llm_client and llm_client.verify_connection():
            health_status["components"]["llm"] = "healthy"
        else:
            health_status["components"]["llm"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception:
        health_status["components"]["llm"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查 Embedding
    if embedding_client:
        health_status["components"]["embedding"] = "healthy"
    else:
        health_status["components"]["embedding"] = "unhealthy"
        health_status["status"] = "degraded"

    return health_status


@app.post("/api/query", response_model=QueryResponse, tags=["查询"])
async def query(
        request: QueryRequest,
        pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """
    处理用户查询

    - **question**: 用户问题
    - **use_graph**: 是否使用图检索
    - **use_vector**: 是否使用向量检索
    - **top_k**: 返回结果数量
    """
    import time
    start_time = time.time()

    try:
        logger.info(f"收到查询: {request.question}")

        # 调用 RAG 流水线
        result = pipeline.answer(
            query=request.question,
            use_graph=request.use_graph,
            use_vector=request.use_vector,
            top_k=request.top_k
        )

        processing_time = time.time() - start_time

        response = QueryResponse(
            question=request.question,
            answer=result.get("answer", "抱歉，我无法回答这个问题。"),
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            processing_time=processing_time
        )

        logger.info(f"查询完成，耗时: {processing_time:.2f}秒")
        return response

    except Exception as e:
        logger.error(f"查询处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询处理失败: {str(e)}")


@app.get("/api/stats", tags=["统计"])
async def get_statistics(client: Neo4jClient = Depends(get_neo4j_client)):
    """获取知识图谱统计信息"""
    try:
        stats = client.get_statistics()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/entity", tags=["知识管理"])
async def create_entity(
        request: EntityRequest,
        client: Neo4jClient = Depends(get_neo4j_client)
):
    """创建实体节点"""
    try:
        result = client.create_node(
            label=request.type,
            properties={
                "name": request.name,
                "description": request.description or ""
            }
        )
        return {
            "success": True,
            "message": "实体创建成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"实体创建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/relation", tags=["知识管理"])
async def create_relation(
        request: RelationRequest,
        client: Neo4jClient = Depends(get_neo4j_client)
):
    """创建实体关系"""
    try:
        # 查找实体
        query = """
        MATCH (a {name: $subject}), (b {name: $object})
        MERGE (a)-[r:%s]->(b)
        RETURN r
        """ % request.predicate

        result = client.execute_write(
            query,
            {"subject": request.subject, "object": request.object}
        )

        return {
            "success": True,
            "message": "关系创建成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"关系创建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/import", tags=["知识管理"])
async def import_knowledge(
        request: KnowledgeImportRequest,
        pipeline: RAGPipeline = Depends(get_rag_pipeline)
):
    """导入知识文本"""
    try:
        from kg.builder import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )

        result = builder.process_text(request.text)

        return {
            "success": True,
            "message": "知识导入成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"知识导入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/data", response_model=GraphDataResponse, tags=["图谱可视化"])
async def get_graph_data(
        node_label: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
):
    """获取图谱数据用于前端可视化"""
    try:
        nodes, edges = graph_retriever.get_graph_data(
            node_label=node_label,
            limit=limit,
            offset=offset
        )

        return GraphDataResponse(nodes=nodes, edges=edges)

    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@app.get("/api/entities/{entity_type}", tags=["查询"])
async def list_entities(
        entity_type: str,
        limit: int = 100,
        client: Neo4jClient = Depends(get_neo4j_client)
):
    """列出指定类型的实体"""
    try:
        entities = client.find_nodes(
            label=entity_type,
            limit=limit
        )
        return {
            "success": True,
            "count": len(entities),
            "data": entities
        }
    except Exception as e:
        logger.error(f"查询实体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "detail": "服务器内部错误"
        }
    )


# ==================== 启动事件（备用）====================

# 如果不使用 lifespan，可以使用这些事件处理器
# @app.on_event("startup")
# async def startup_event():
#     """应用启动事件"""
#     pass

# @app.on_event("shutdown")
# async def shutdown_event():
#     """应用关闭事件"""
#     pass


if __name__ == "__main__":
    # 直接运行此文件时的启动方式（不推荐，请使用 run.py）
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
