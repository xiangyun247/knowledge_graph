"""
RAG 流水线
整合检索和生成的完整流程
支持图检索、向量检索、混合检索
"""

import config
from typing import Dict, Any, List, Optional
import logging
import time
from llm.client import LLMClient, EmbeddingClient
from db.neo4j_client import Neo4jClient
from rag.query_parser import QueryParser
from rag.graph_retriever import GraphRetriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG 流水线"""

    def __init__(
            self,
            neo4j_client: Neo4jClient,
            llm_client: LLMClient,
            embedding_client: EmbeddingClient
    ):
        """
        初始化 RAG 流水线

        Args:
            neo4j_client: Neo4j 客户端
            llm_client: LLM 客户端
            embedding_client: Embedding 客户端
        """
        self.neo4j = neo4j_client
        self.llm = llm_client
        self.embedding = embedding_client

        # 初始化组件
        self.query_parser = QueryParser(llm_client)
        self.graph_retriever = GraphRetriever(neo4j_client)

        # 从 config 读取配置
        self.vector_top_k = config.VECTOR_TOP_K
        self.max_graph_depth = config.MAX_GRAPH_DEPTH
        self.max_context_length = 3000  # 上下文最大长度

        logger.info("RAG 流水线初始化完成")

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
        """简单的意图分类"""
        if any(word in question for word in ['症状', '表现', '怎么样']):
            return 'symptom_query'
        elif any(word in question for word in ['治疗', '怎么治', '用药']):
            return 'treatment_query'
        elif any(word in question for word in ['科室', '挂号', '看什么科']):
            return 'department_query'
        else:
            return 'general_query'

    def _extract_entities(self, question: str) -> List[str]:
        """简单的实体提取"""
        entities = []
        # 这里可以集成更复杂的NER模型
        # 简单实现：搜索已知疾病名
        disease_keywords = ['胰腺炎', '糖尿病', '高血压', '急性胰腺炎', '慢性胰腺炎']
        for keyword in disease_keywords:
            if keyword in question:
                entities.append(keyword)
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
                        node = record['e']
                        rel_type = record.get('rel_type')
                        related = record.get('related')

                        knowledge.append({
                            'entity': node.get('name', ''),
                            'type': list(node.labels)[0] if node.labels else 'Unknown',
                            'properties': dict(node),
                            'relation': rel_type,
                            'related_entity': related.get('name', '') if related else None
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

        # 根据意图组织答案
        if intent == 'symptom_query':
            symptoms = [k for k in knowledge if k.get('relation') == 'HAS_SYMPTOM']
            if symptoms:
                symptom_list = [s.get('related_entity', '') for s in symptoms if s.get('related_entity')]
                return f"根据医疗知识库，主要症状包括：{', '.join(symptom_list)}。建议及时就医。"

        elif intent == 'treatment_query':
            treatments = [k for k in knowledge if k.get('relation') == 'TREATS']
            if treatments:
                drug_list = [t.get('entity', '') for t in treatments]
                return f"常用治疗方法包括：{', '.join(drug_list)}。请遵医嘱用药。"

        elif intent == 'department_query':
            departments = [k for k in knowledge if k.get('relation') == 'BELONGS_TO']
            if departments:
                dept_list = [d.get('related_entity', '') for d in departments if d.get('related_entity')]
                return f"建议挂号科室：{', '.join(dept_list)}。"

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
            top_k: Optional[int] = None,
            return_sources: bool = True
    ) -> Dict[str, Any]:
        """
        回答用户问题（完整版，支持更多配置）

        Args:
            query: 用户问题
            use_graph: 是否使用图检索
            use_vector: 是否使用向量检索
            top_k: 返回结果数量
            return_sources: 是否返回信息来源

        Returns:
            回答结果字典
        """
        start_time = time.time()

        logger.info(f"开始处理查询: {query}")
        logger.info(f"检索策略: 图检索={use_graph}, 向量检索={use_vector}")

        try:
            # 1. 查询解析
            logger.info("步骤 1/4: 解析查询...")
            parsed_query = self.query_parser.parse(query)
            logger.info(f"[OK] 查询解析完成: 意图={parsed_query['intent']}, 实体数={len(parsed_query['entities'])}")

            # 2. 信息检索
            logger.info("步骤 2/4: 检索相关信息...")
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

        # 1. 图检索
        if use_graph and entity_names:
            logger.info(f"执行图检索: 实体={entity_names}")
            try:
                graph_results = self.graph_retriever.retrieve(
                    query=query_text,
                    entity_names=entity_names,
                    max_depth=self.max_graph_depth,
                    limit=top_k
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
            keywords = parsed_query.get("keywords", [])
            if keywords:
                try:
                    keyword_results = self._keyword_search(keywords, limit=top_k)
                    logger.info(f"关键词检索返回 {len(keyword_results)} 条结果")
                    all_results.extend(keyword_results)
                except Exception as e:
                    logger.error(f"关键词检索失败: {e}")

        # 4. 去重和排序
        all_results = self._deduplicate_and_rank(all_results)

        return all_results[:top_k * 2]

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
        base_prompt = "你是一个专业的医学问答助手，擅长回答胰腺炎相关问题。"

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
            "什么是重症急性胰腺炎？",
            "胰腺炎有哪些症状？",
            "如何治疗急性胰腺炎？"
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
