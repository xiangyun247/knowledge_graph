"""
RAG 流水线
整合检索和生成的完整流程
支持图检索、向量检索、混合检索（Hybrid RAG）
"""

import config
from typing import Dict, Any, List, Optional
import logging
import time
from llm.client import LLMClient, EmbeddingClient
from db.neo4j_client import Neo4jClient
from rag.query_parser import QueryParser
from rag.graph_retriever import GraphRetriever
from rag import hybrid_retriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG 流水线"""

    def __init__(
            self,
            neo4j_client: Neo4jClient,
            llm_client: LLMClient,
            embedding_client: EmbeddingClient,
            chroma_store: Optional[Any] = None,
            mysql_client: Optional[Any] = None,
    ):
        """
        初始化 RAG 流水线

        Args:
            neo4j_client: Neo4j 客户端
            llm_client: LLM 客户端
            embedding_client: Embedding 客户端
            chroma_store: Chroma 向量库（可选），用于 Hybrid RAG 文档检索
            mysql_client: MySQL 客户端（可选），用于 Hybrid RAG 图检索时按 user_id 过滤
        """
        self.neo4j = neo4j_client
        self.llm = llm_client
        self.embedding = embedding_client
        self._chroma_store = chroma_store
        self._mysql_client = mysql_client

        # 初始化组件
        self.query_parser = QueryParser(llm_client)
        self.graph_retriever = GraphRetriever(neo4j_client)

        # 从 config 读取配置
        self.vector_top_k = config.VECTOR_TOP_K
        self.max_graph_depth = config.MAX_GRAPH_DEPTH
        self.max_context_length = 3000  # 上下文最大长度

        # 意图 → 优先检索的关系类型（表3）
        self.intent_to_relations = {
            "symptom": ["HAS_SYMPTOM"],
            "treatment": ["TREATED_BY", "TREATS_COMPLICATION"],
            "cause": ["HAS_ETIOLOGY"],
            "diagnosis": ["REQUIRES_EXAM", "HAS_ABNORMAL_EXAM_RESULT"],
            "prevention": ["PREVENTED_BY"],
            "complication": ["HAS_COMPLICATION"],
            "prognosis": ["HAS_PROGNOSIS"],
            "population": ["AFFECTS_POPULATION"],
            "department": ["BELONGS_TO_DEPARTMENT", "TREATED_AT_HOSPITAL"],
            "comparison": ["DIFFERENTIAL_DIAGNOSIS"],
        }

        logger.info("RAG 流水线初始化完成")

    def _get_chroma_store(self) -> Optional[Any]:
        """获取 ChromaStore，未传入时尝试懒加载。"""
        if self._chroma_store is not None:
            return self._chroma_store
        try:
            from backend.chroma_store import ChromaStore
            self._chroma_store = ChromaStore()
            return self._chroma_store
        except Exception as e:
            logger.debug("ChromaStore 不可用，跳过文档向量检索: %s", e)
            return None

    def _get_mysql_client(self) -> Optional[Any]:
        """获取 MySQL 客户端，未传入时尝试懒加载。"""
        if self._mysql_client is not None:
            return self._mysql_client
        try:
            from db.mysql_client import get_mysql_client
            self._mysql_client = get_mysql_client()
            return self._mysql_client
        except Exception as e:
            logger.debug("MySQL 不可用，跳过用户图谱过滤: %s", e)
            return None

    # ✅ 新增：简化版 query 方法（主要对外接口）
    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        执行 RAG 查询（简化版接口）

        Args:
            question: 用户问题
            top_k: 返回top-k个相关结果

        Returns:
            包含答案和来源的字典
        """
        try:
            logger.info(f"处理查询: {question}")

            # 1. 查询意图识别
            intent = self._classify_intent(question)
            logger.info(f"查询意图: {intent}")

            # 2. 实体识别
            entities = self._extract_entities(question)
            logger.info(f"识别到的实体: {entities}")

            # 3. 知识检索
            retrieved_knowledge = self._retrieve_knowledge(question, entities, top_k)
            logger.info(f"检索到 {len(retrieved_knowledge)} 条知识")

            # 4. 生成答案
            answer = self._generate_answer_simple(question, retrieved_knowledge, intent)

            # 5. 构建响应
            response = {
                "question": question,
                "answer": answer,
                "context": retrieved_knowledge,  # ✅ 新增
                "entities": entities,  # ✅ 移到外层
                "sources": retrieved_knowledge,
                "query_info": {
                    "intent": intent,
                    "retrieved_count": len(retrieved_knowledge)
                }
            }

            return response

        except Exception as e:
            logger.error(f"RAG查询失败: {e}")
            import traceback
            traceback.print_exc()

            return {
                "question": question,
                "answer": f"抱歉，查询过程中出现错误: {str(e)}",
                "sources": [],
                "query_info": {
                    "intent": "unknown",
                    "entities": [],
                    "retrieved_count": 0
                }
            }

    def _classify_intent(self, question: str) -> str:
        """简单的意图分类（与 QueryParser.intent_types 对齐）"""
        q = question.lower()
        if any(w in q for w in ['症状', '表现', '特征', '感觉', '体征']):
            return 'symptom_query'
        elif any(w in q for w in ['治疗', '怎么治', '用药', '疗法', '手术']):
            return 'treatment_query'
        elif any(w in q for w in ['科室', '挂号', '看什么科', '就诊']):
            return 'department_query'
        elif any(w in q for w in ['预后', '恢复', '治愈', '能好吗']):
            return 'prognosis_query'
        elif any(w in q for w in ['多发', '人群', '哪些人', '好发于']):
            return 'population_query'
        elif any(w in q for w in ['原因', '为什么', '病因', '导致']):
            return 'cause_query'
        elif any(w in q for w in ['检查', '诊断', '确诊']):
            return 'diagnosis_query'
        elif any(w in q for w in ['并发症', '后果', '影响']):
            return 'complication_query'
        else:
            return 'general_query'

    def _extract_entities(self, question: str) -> List[str]:
        """简单的实体提取（可复用 QueryParser 或扩展关键词）"""
        entities = []
        keywords = [
            '轻度认知障碍', '阿尔茨海默', '记忆减退', '老年痴呆',
            '川崎病', '糖尿病', '高血压', '冠心病',
        ]
        for kw in keywords:
            if kw in question:
                entities.append(kw)
        if not entities:
            import re
            words = re.findall(r'[\u4e00-\u9fa5]{2,6}', question)
            for w in words:
                if any(x in w for x in ['炎', '病', '症', '瘤']):
                    entities.append(w)
                    break
        return entities

    def _retrieve_knowledge(self, question: str, entities: List[str], top_k: int) -> List[Dict]:
        """检索相关知识"""
        knowledge = []

        try:
            # 如果识别到实体，优先查询实体信息
            if entities:
                for entity in entities:
                    # 查询实体及其关系
                    query = """
                    MATCH (e {name: $entity_name})
                    OPTIONAL MATCH (e)-[r]->(related)
                    RETURN e, type(r) as rel_type, related
                    LIMIT $limit
                    """
                    results = self.neo4j.execute_query(
                        query,
                        {"entity_name": entity, "limit": top_k}
                    )

                    for record in results:
                        # Neo4jClient.execute_query() 返回的是普通 dict，而不是 neo4j.Node
                        node = record.get("e") or {}
                        rel_type = record.get("rel_type")
                        related = record.get("related") or {}

                        # labels 可能在 record["labels"]，也可能在节点属性里
                        labels = record.get("labels") or node.get("labels") or []
                        if not isinstance(labels, list):
                            labels = [labels]

                        knowledge.append({
                            "entity": node.get("name", ""),
                            "type": labels[0] if labels else "Unknown",
                            "properties": node,
                            "relation": rel_type,
                            "related_entity": related.get("name") if related else None,
                        })

            # 如果没有实体或知识不足，使用关键词搜索
            if len(knowledge) < top_k:
                search_results = self.neo4j.search_entities(question, limit=top_k)
                for result in search_results:
                    if result not in knowledge:
                        knowledge.append(result)

            return knowledge[:top_k]

        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            return []

    def _generate_answer_simple(self, question: str, knowledge: List[Dict], intent: str) -> str:
        """基于检索的知识生成答案（简化版）"""
        if not knowledge:
            return "抱歉，我没有找到相关的医疗信息。请咨询专业医生。"

        # 根据意图组织答案（使用表3 关系类型）
        if intent == 'symptom_query':
            symptoms = [k for k in knowledge if k.get('relation') == 'HAS_SYMPTOM']
            if symptoms:
                symptom_list = [s.get('related_entity', '') for s in symptoms if s.get('related_entity')]
                return f"根据医疗知识库，主要症状包括：{', '.join(symptom_list)}。建议及时就医。"

        elif intent == 'treatment_query':
            treatments = [k for k in knowledge if k.get('relation') in ('TREATED_BY', 'TREATS_COMPLICATION')]
            if treatments:
                items = [t.get('related_entity') or t.get('entity', '') for t in treatments]
                items = [x for x in items if x]
                if items:
                    return f"常用治疗方法包括：{', '.join(items)}。请遵医嘱用药。"

        elif intent == 'department_query':
            depts = [k for k in knowledge if k.get('relation') in ('BELONGS_TO_DEPARTMENT', 'TREATED_AT_HOSPITAL')]
            if depts:
                dept_list = [d.get('related_entity', '') for d in depts if d.get('related_entity')]
                if dept_list:
                    return f"建议挂号科室：{', '.join(dept_list)}。"

        elif intent == 'prognosis_query':
            prog = [k for k in knowledge if k.get('relation') == 'HAS_PROGNOSIS']
            if prog:
                p_list = [p.get('related_entity', '') for p in prog if p.get('related_entity')]
                if p_list:
                    return f"预后情况：{', '.join(p_list)}。具体请咨询主治医生。"

        elif intent == 'population_query':
            pop = [k for k in knowledge if k.get('relation') == 'AFFECTS_POPULATION']
            if pop:
                p_list = [p.get('related_entity', '') for p in pop if p.get('related_entity')]
                if p_list:
                    return f"多发人群：{', '.join(p_list)}。"

        elif intent == 'diagnosis_query':
            exams = [k for k in knowledge if k.get('relation') in ('REQUIRES_EXAM', 'HAS_ABNORMAL_EXAM_RESULT')]
            if exams:
                e_list = [e.get('related_entity', '') for e in exams if e.get('related_entity')]
                if e_list:
                    return f"相关检查包括：{', '.join(e_list)}。"

        # 通用回答
        entity_info = knowledge[0]
        entity_name = entity_info.get('entity', entity_info.get('name', ''))
        description = entity_info.get('properties', {}).get('description', '')

        answer = f"关于{entity_name}"
        if description:
            answer += f"：{description}"

        return answer + " 详细信息请咨询专业医生。"



    # ================== 以下是原有的完整 answer 方法 ==================

    def answer(
            self,
            query: str,
            use_graph: bool = True,
            use_vector: bool = True,
            use_hybrid: bool = False,
            top_k: Optional[int] = None,
            return_sources: bool = True,
            user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        回答用户问题（完整版，支持更多配置）

        Args:
            query: 用户问题
            use_graph: 是否使用图检索（use_hybrid=False 时生效）
            use_vector: 是否使用向量检索（use_hybrid=False 时生效）
            use_hybrid: 是否使用混合检索（图+Chroma+关键词，RRF 融合）
            top_k: 返回结果数量
            return_sources: 是否返回信息来源
            user_id: 用户 ID（use_hybrid 时用于 Chroma 文档过滤）

        Returns:
            回答结果字典
        """
        start_time = time.time()

        logger.info(f"开始处理查询: {query}")
        if use_hybrid:
            logger.info("检索策略: 混合检索（图+文档+关键词 RRF）")
        else:
            logger.info(f"检索策略: 图检索={use_graph}, 向量检索={use_vector}")

        try:
            # 1. 查询解析
            logger.info("步骤 1/4: 解析查询...")
            parsed_query = self.query_parser.parse(query)
            parsed_query.setdefault("query", query)
            logger.info(f"[OK] 查询解析完成: 意图={parsed_query['intent']}, 实体数={len(parsed_query['entities'])}")

            # 2. 信息检索
            logger.info("步骤 2/4: 检索相关信息...")
            if use_hybrid:
                hybrid_items = self._retrieve_hybrid(
                    parsed_query,
                    top_k=top_k or self.vector_top_k,
                    top_k_per_source=15,
                    use_graph=True,
                    use_doc_vector=True,
                    use_keyword=True,
                    user_id=user_id,
                )
                retrieval_results = self._hybrid_items_to_sources(hybrid_items)
            else:
                retrieval_results = self._retrieve_information(
                    parsed_query,
                    use_graph=use_graph,
                    use_vector=use_vector,
                    top_k=top_k or self.vector_top_k
                )
            logger.info(f"[OK] 信息检索完成: 共检索到 {len(retrieval_results)} 条信息")

            # 3. 构建上下文
            logger.info("步骤 3/4: 构建上下文...")
            context = self._build_context(retrieval_results, parsed_query)
            logger.info(f"[OK] 上下文构建完成: {len(context)} 字符")

            # 4. 生成答案
            logger.info("步骤 4/4: 生成答案...")
            answer = self._generate_answer(query, context, parsed_query)
            logger.info(f"[OK] 答案生成完成: {len(answer)} 字符")

            # 计算处理时间
            processing_time = time.time() - start_time

            # 将信息来源中的 Neo4j 时间等不可 JSON 序列化对象转换为字符串
            def _normalize(obj: Any) -> Any:
                try:
                    if isinstance(obj, (str, int, float, bool)) or obj is None:
                        return obj
                    if isinstance(obj, list):
                        return [_normalize(x) for x in obj]
                    if isinstance(obj, dict):
                        return {k: _normalize(v) for k, v in obj.items()}
                    # 其他类型（例如 neo4j.time.DateTime）统一转为字符串
                    return str(obj)
                except Exception:
                    return str(obj)

            safe_sources = [_normalize(s) for s in retrieval_results] if return_sources else []

            # 构建响应
            response = {
                "query": query,
                "answer": answer,
                "sources": safe_sources,
                "confidence": self._calculate_confidence(retrieval_results, parsed_query),
                "processing_time": processing_time,
                "metadata": {
                    "parsed_intent": parsed_query.get("intent"),
                    "parsed_entities": [e["name"] for e in parsed_query.get("entities", [])],
                    "retrieval_count": len(retrieval_results),
                    "context_length": len(context)
                }
            }

            logger.info(f"查询处理完成，耗时: {processing_time:.2f}秒")
            return response

        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            import traceback
            traceback.print_exc()

            return {
                "query": query,
                "answer": "抱歉，处理您的问题时遇到了错误。请稍后重试或换个方式提问。",
                "sources": [],
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "error": str(e)
            }

    def _retrieve_information(
            self,
            parsed_query: Dict[str, Any],
            use_graph: bool = True,
            use_vector: bool = True,
            top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """检索相关信息（支持多种检索策略）"""
        all_results = []

        # 提取实体名称
        entity_names = [e["name"] for e in parsed_query.get("entities", [])]
        query_text = parsed_query.get("normalized_query", "")

        # 1. 图检索（按意图优先相关关系类型）
        if use_graph and entity_names:
            intent = parsed_query.get("intent", "other")
            preferred = self.intent_to_relations.get(intent)
            logger.info(f"执行图检索: 实体={entity_names}, 意图={intent}")
            try:
                graph_results = self.graph_retriever.retrieve(
                    query=query_text,
                    entity_names=entity_names,
                    max_depth=self.max_graph_depth,
                    limit=top_k,
                    preferred_relation_types=preferred,
                )
                logger.info(f"图检索返回 {len(graph_results)} 条结果")
                all_results.extend(graph_results)
            except Exception as e:
                logger.error(f"图检索失败: {e}")

        # 2. 向量检索
        if use_vector:
            logger.info("执行向量检索")
            try:
                vector_results = self._vector_search(query_text, top_k=top_k)
                logger.info(f"向量检索返回 {len(vector_results)} 条结果")
                all_results.extend(vector_results)
            except Exception as e:
                logger.error(f"向量检索失败: {e}")

        # 3. 如果没有任何结果，尝试关键词检索
        if not all_results:
            logger.warning("图检索和向量检索均无结果，尝试关键词检索")
            keywords = parsed_query.get("keywords", []) or ([query_text] if query_text else [])
            if keywords:
                try:
                    keyword_results = self._keyword_search(keywords, limit=top_k)
                    logger.info(f"关键词检索返回 {len(keyword_results)} 条结果")
                    all_results.extend(keyword_results)
                except Exception as e:
                    logger.error(f"关键词检索失败: {e}")

        # 3.5 空结果兜底：用 query 分词做二次关键词检索
        if not all_results and query_text:
            try:
                import re
                words = [w for w in re.findall(r"[\u4e00-\u9fff\w]+", query_text) if len(w) >= 2][:5]
                if words:
                    fallback = self._keyword_search(words, limit=top_k)
                    if fallback:
                        all_results.extend(fallback)
                        logger.info("空结果兜底(关键词分词): %d 条", len(fallback))
            except Exception as e:
                logger.debug("空结果兜底失败: %s", e)

        # 4. 去重和排序
        all_results = self._deduplicate_and_rank(all_results)

        return all_results[:top_k * 2]

    def _retrieve_hybrid(
        self,
        parsed_query: Dict[str, Any],
        *,
        top_k: int = 10,
        top_k_per_source: int = 15,
        use_graph: bool = True,
        use_doc_vector: bool = True,
        use_keyword: bool = True,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        混合检索：图 + Chroma 文档 + 关键词，RRF 融合。

        Returns:
            List[HybridItem]，按 RRF 分数降序，每项含 content、source、rrf_score、raw 等
        """
        entity_names = [e["name"] for e in parsed_query.get("entities", [])]
        query_text = parsed_query.get("normalized_query", parsed_query.get("query", ""))

        graph_items: List[Dict[str, Any]] = []
        doc_items: List[Dict[str, Any]] = []
        keyword_items: List[Dict[str, Any]] = []

        # 1. 图检索（user_id 时优先 MySQL 用户图谱，否则 Neo4j）
        if use_graph and entity_names:
            try:
                graph_results: List[Dict[str, Any]] = []
                if user_id:
                    mc = self._get_mysql_client()
                    if mc:
                        from rag.mysql_graph_retriever import retrieve_from_mysql_graphs
                        graph_results = retrieve_from_mysql_graphs(
                            mc,
                            entity_names=entity_names,
                            user_id=user_id,
                            graph_id=None,
                            max_depth=self.max_graph_depth,
                            limit=top_k_per_source,
                        )
                        if graph_results:
                            logger.info("混合检索-图(MySQL 用户图谱): %d 条", len(graph_results))
                if not graph_results:
                    intent = parsed_query.get("intent", "other")
                    preferred = self.intent_to_relations.get(intent)
                    graph_results = self.graph_retriever.retrieve(
                        query=query_text,
                        entity_names=entity_names,
                        max_depth=self.max_graph_depth,
                        limit=top_k_per_source,
                        preferred_relation_types=preferred,
                    )
                    if graph_results:
                        logger.info("混合检索-图(Neo4j): %d 条", len(graph_results))
                graph_items = hybrid_retriever.graph_results_to_hybrid(
                    graph_results, top_k_per_source=top_k_per_source
                )
                logger.info("混合检索-图: %d 条", len(graph_items))
            except Exception as e:
                logger.error("混合检索-图失败: %s", e)

        # 2. Chroma 文档检索
        if use_doc_vector:
            chroma = self._get_chroma_store()
            if chroma:
                try:
                    where = {"user_id": user_id} if user_id else None
                    doc_results = chroma.search(
                        query_text, k=top_k_per_source, where=where
                    )
                    doc_items = hybrid_retriever.chroma_results_to_hybrid(
                        doc_results, top_k_per_source=top_k_per_source
                    )
                    logger.info("混合检索-文档: %d 条", len(doc_items))
                except Exception as e:
                    logger.error("混合检索-文档失败: %s", e)

        # 3. 关键词检索
        if use_keyword:
            try:
                keywords = parsed_query.get("keywords", []) or [query_text]
                kw_results = self._keyword_search(keywords, limit=top_k_per_source)
                keyword_items = hybrid_retriever.keyword_results_to_hybrid(
                    kw_results, top_k_per_source=top_k_per_source
                )
                logger.info("混合检索-关键词: %d 条", len(keyword_items))
            except Exception as e:
                logger.error("混合检索-关键词失败: %s", e)

        # 4. RRF 融合
        fused = hybrid_retriever.fuse_hybrid_three_way(
            graph_items, doc_items, keyword_items, k=hybrid_retriever.DEFAULT_RRF_K
        )
        logger.info("混合检索-RRF 融合: %d 条", len(fused))

        # 5. 空结果兜底：用 query 分词做二次关键词检索
        if not fused and query_text:
            try:
                import re
                words = [w for w in re.findall(r"[\u4e00-\u9fff\w]+", query_text) if len(w) >= 2][:5]
                if words:
                    fallback_kw = self._keyword_search(words, limit=top_k_per_source)
                    if fallback_kw:
                        fallback_items = hybrid_retriever.keyword_results_to_hybrid(
                            fallback_kw, top_k_per_source=top_k_per_source
                        )
                        fused = fallback_items[:top_k]
                        logger.info("混合检索-空结果兜底(关键词): %d 条", len(fused))
            except Exception as e:
                logger.debug("空结果兜底失败: %s", e)

        return fused[:top_k]

    def _hybrid_items_to_sources(
        self, hybrid_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将 HybridItem 列表转为 _build_context / _format_single_result 可用的格式。
        """
        results = []
        for i, item in enumerate(hybrid_items):
            content = item.get("content", "")
            results.append({
                "type": item.get("source", "unknown"),
                "name": (content[:50] + "..." if len(content) > 50 else content) or "来源",
                "description": content,
                "relevance_score": item.get("rrf_score", 0),
                "labels": [item.get("source", "")],
                "content_key": item.get("content_key"),
                "raw": item.get("raw"),
            })
        return results

    def _vector_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """向量检索"""
        try:
            # 1. 生成查询向量
            query_embedding = self.embedding.encode_single(query)

            # 2. 在 Neo4j 中搜索
            cypher_query = """
            MATCH (n)
            WHERE n.description IS NOT NULL
            RETURN n, labels(n) as labels, id(n) as node_id
            LIMIT $limit
            """

            records = self.neo4j.execute_query(
                cypher_query,
                {"limit": top_k * 3}
            )

            results = []
            for record in records:
                node = record["n"]
                description = node.get("description", "")

                if description:
                    desc_embedding = self.embedding.encode_single(description)
                    similarity = self._cosine_similarity(query_embedding, desc_embedding)

                    results.append({
                        "type": "vector_match",
                        "node_id": record["node_id"],
                        "labels": record["labels"],
                        "name": node.get("name", ""),
                        "description": description,
                        "properties": dict(node),
                        "relevance_score": similarity,
                        "source": "vector_search"
                    })

            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    def _keyword_search(self, keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        """关键词检索（备用方案）"""
        if not keywords:
            return []

        query = """
        MATCH (n)
        WHERE any(keyword IN $keywords WHERE 
            n.name CONTAINS keyword OR 
            n.description CONTAINS keyword
        )
        RETURN n, labels(n) as labels, id(n) as node_id
        LIMIT $limit
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"keywords": keywords, "limit": limit}
            )

            results = []
            for record in records:
                node = record["n"]
                results.append({
                    "type": "keyword_match",
                    "node_id": record["node_id"],
                    "labels": record["labels"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "properties": dict(node),
                    "relevance_score": 0.5,
                    "source": "keyword_search"
                })

            return results

        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _deduplicate_and_rank(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重并排序结果"""
        unique_results = {}

        for result in results:
            key = result.get("node_id") or result.get("name") or str(result)

            if key in unique_results:
                if result.get("relevance_score", 0) > unique_results[key].get("relevance_score", 0):
                    unique_results[key] = result
            else:
                unique_results[key] = result

        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )

        return sorted_results

    def _build_context(
            self,
            retrieval_results: List[Dict[str, Any]],
            parsed_query: Dict[str, Any]
    ) -> str:
        """构建 LLM 上下文"""
        if not retrieval_results:
            return "未找到相关信息。"

        context_parts = []
        current_length = 0

        intent = parsed_query.get("intent", "other")
        context_parts.append(f"查询意图: {intent}\n\n")
        current_length += len(context_parts[-1])

        context_parts.append("相关知识:\n")
        current_length += len(context_parts[-1])

        for i, result in enumerate(retrieval_results):
            if current_length >= self.max_context_length:
                break

            result_text = self._format_single_result(result, i + 1)

            if current_length + len(result_text) > self.max_context_length:
                break

            context_parts.append(result_text)
            current_length += len(result_text)

        context = "".join(context_parts)
        return context

    def _format_single_result(self, result: Dict[str, Any], index: int) -> str:
        """格式化单个检索结果"""
        result_type = result.get("type", "unknown")
        name = result.get("name", "未知")
        description = result.get("description", "")
        relevance = result.get("relevance_score", 0)

        text = f"\n[{index}] {name}"

        if result.get("labels"):
            text += f" ({', '.join(result['labels'])})"

        text += f" [相关度: {relevance:.2f}]\n"

        if description:
            text += f"描述: {description}\n"

        if result_type == "neighbor":
            hop_count = result.get("hop_count", 0)
            text += f"路径距离: {hop_count} 跳\n"

        elif result_type == "path":
            path_nodes = result.get("path_nodes", [])
            if path_nodes:
                path_str = " -> ".join([n.get("name", "") for n in path_nodes])
                text += f"关系路径: {path_str}\n"

        return text

    def _generate_answer(
            self,
            query: str,
            context: str,
            parsed_query: Dict[str, Any]
    ) -> str:
        """生成答案"""
        intent = parsed_query.get("intent", "other")

        system_prompt = self._build_system_prompt(intent)
        user_prompt = self._build_user_prompt(query, context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            answer = self.llm.chat(
                messages,
                temperature=0.7,
                max_tokens=500
            )

            return answer.strip()

        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            return "抱歉，生成答案时遇到了问题。"

    def _build_system_prompt(self, intent: str) -> str:
        """构建系统提示词"""
        base_prompt = "你是一个专业的医学问答助手，擅长回答老年认知障碍、认知负荷与日常照护相关问题。"

        intent_prompts = {
            "definition": "请用简洁准确的语言解释医学概念。",
            "symptom": "请详细列举症状，并说明严重程度。",
            "treatment": "请提供治疗建议，包括药物和非药物治疗。",
            "cause": "请解释病因和发病机制。",
            "diagnosis": "请说明诊断方法和检查项目。",
            "prevention": "请提供预防建议和注意事项。",
            "complication": "请说明可能的并发症和后果。",
            "comparison": "请客观比较不同选项的异同。"
        }

        specific_prompt = intent_prompts.get(intent, "请根据提供的信息回答问题。")

        full_prompt = f"""{base_prompt}

{specific_prompt}

要求:
1. 基于提供的知识库信息回答
2. 如果知识库中没有相关信息，诚实地说明
3. 回答要准确、专业、易懂
4. 必要时提醒患者就医
5. 不要编造信息
"""

        return full_prompt

    def _build_user_prompt(self, query: str, context: str) -> str:
        """构建用户提示词"""
        return f"""请根据以下知识库信息回答问题。

{context}

问题: {query}

请提供详细、准确的回答:"""

    def _calculate_confidence(
            self,
            retrieval_results: List[Dict[str, Any]],
            parsed_query: Dict[str, Any]
    ) -> float:
        """计算回答置信度"""
        if not retrieval_results:
            return 0.0

        base_confidence = 0.5

        result_count = len(retrieval_results)
        if result_count >= 5:
            base_confidence += 0.2
        elif result_count >= 3:
            base_confidence += 0.1

        avg_relevance = sum(r.get("relevance_score", 0) for r in retrieval_results) / len(retrieval_results)
        base_confidence += avg_relevance * 0.2

        parse_confidence = parsed_query.get("confidence", 0.5)
        base_confidence = (base_confidence + parse_confidence) / 2

        return min(1.0, max(0.0, base_confidence))


# 示例用法
if __name__ == "__main__":
    import logging
    from db.neo4j_client import Neo4jClient
    from llm.client import LLMClient, EmbeddingClient

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("RAG 流水线测试")
    print("=" * 60)

    neo4j_client = Neo4jClient()
    llm_client = LLMClient()
    embedding_client = EmbeddingClient()

    try:
        pipeline = RAGPipeline(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )

        test_queries = [
            "什么是轻度认知障碍？",
            "认知障碍老人日常要注意什么？",
            "如何降低老人使用产品时的认知负荷？"
        ]

        for query in test_queries:
            print(f"\n{'=' * 60}")
            print(f"问题: {query}")
            print("=" * 60)

            # 测试简化版 query 方法
            result = pipeline.query(query)

            print(f"\n答案:\n{result['answer']}")
            print(f"\n信息来源数: {len(result['sources'])}")

    finally:
        neo4j_client.close()
        llm_client.close()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
