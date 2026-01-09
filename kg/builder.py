"""
知识图谱构建器
从文本中提取实体和关系，构建知识图谱
"""

import config  # ✅ 修改这里
from typing import List, Dict, Any, Optional
import logging
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """文本预处理器"""

    def __init__(self):
        """初始化文本预处理器"""
        pass

    def clean_text(self, text: str) -> str:
        """
        清理文本（支持中英文）

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 移除多余空白
        text = " ".join(text.split())

        # 移除特殊字符（保留中英文、数字、常用标点）
        import re
        # 同时支持中英文标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''（）【】《》\-\.\?!\s]', '', text)

        return text.strip()

    def split_sentences(self, text: str) -> List[str]:
        """
        将文本分割为句子（支持中英文）

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        import re
        # 同时支持中文和英文标点分割
        sentences = re.split(r'[。！？\.\?!\n]+', text)

        # 过滤空句子
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        提取关键词（简单版本，基于词频）

        Args:
            text: 输入文本
            top_k: 返回前 k 个关键词

        Returns:
            关键词列表
        """
        # 简单的词频统计（实际应用中可以使用 jieba 或其他 NLP 工具）
        import re
        from collections import Counter

        # 提取中文词汇（2-4个字）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)

        # 统计词频
        word_freq = Counter(words)

        # 返回最常见的词
        return [word for word, _ in word_freq.most_common(top_k)]


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(
            self,
            neo4j_client: Neo4jClient,
            llm_client: LLMClient,
            preprocessor: Optional[TextPreprocessor] = None
    ):
        """
        初始化知识图谱构建器

        Args:
            neo4j_client: Neo4j 客户端
            llm_client: LLM 客户端
            preprocessor: 文本预处理器（可选）
        """
        self.neo4j = neo4j_client
        self.llm = llm_client
        self.preprocessor = preprocessor or TextPreprocessor()

        # 从 config 读取配置
        self.entity_types = config.ENTITY_TYPES  # ✅ 使用 config.XXX
        self.relation_types = config.RELATION_TYPES

        logger.info("知识图谱构建器初始化完成")

    def process_text(self, text: str) -> Dict[str, Any]:
        """
        处理文本，提取实体和关系

        Args:
            text: 输入文本

        Returns:
            处理结果，包含统计信息和实际的实体、关系数据
        """
        try:
            logger.info(f"开始处理文本 (长度: {len(text)})")

            # 1. 文本预处理
            cleaned_text = self.preprocessor.clean_text(text)
            
            # 2. 文本分段处理，每段大约1000个字符，提高处理效率
            logger.info(f"原始文本长度: {len(cleaned_text)} 字符")
            
            # 先按句子分割，再合并成段落
            sentences = self.preprocessor.split_sentences(cleaned_text)
            logger.info(f"文本已分割为 {len(sentences)} 个句子")
            
            # 将句子合并为段落，每段大约1000个字符
            paragraphs = []
            current_paragraph = []
            current_length = 0
            
            for sentence in sentences:
                sentence_length = len(sentence)
                if current_length + sentence_length < 1000:
                    current_paragraph.append(sentence)
                    current_length += sentence_length
                else:
                    if current_paragraph:
                        paragraphs.append("。".join(current_paragraph) + "。")
                    current_paragraph = [sentence]
                    current_length = sentence_length
            
            # 添加最后一个段落
            if current_paragraph:
                paragraphs.append("。".join(current_paragraph) + "。")
            
            logger.info(f"文本已合并为 {len(paragraphs)} 个段落")

            # 3. 提取实体和关系
            entities_created = 0
            relations_created = 0
            
            # 存储所有提取的实体和关系
            all_entities = []
            all_relations = []
            
            # 用于去重的集合
            seen_entities = set()
            seen_relations = set()

            # 处理每个段落
            for i, paragraph in enumerate(paragraphs):
                if not paragraph:
                    continue

                logger.info(f"处理段落 {i + 1}/{len(paragraphs)} (长度: {len(paragraph)} 字符)")

                # 使用 LLM 提取实体和关系
                extraction_result = self._extract_entities_and_relations(paragraph)

                # 处理实体
                for entity in extraction_result.get("entities", []):
                    entity_key = (entity.get("name"), entity.get("type"))
                    if entity_key not in seen_entities:
                        seen_entities.add(entity_key)
                        all_entities.append(entity)
                        try:
                            self._create_entity(entity)
                            entities_created += 1
                        except Exception as e:
                            logger.warning(f"创建实体失败: {entity} - {e}")

                # 处理关系
                for relation in extraction_result.get("relations", []):
                    relation_key = (relation.get("subject"), relation.get("predicate"), relation.get("object"))
                    if relation_key not in seen_relations:
                        seen_relations.add(relation_key)
                        all_relations.append(relation)
                        try:
                            self._create_relation(relation)
                            relations_created += 1
                        except Exception as e:
                            logger.warning(f"创建关系失败: {relation} - {e}")

            # 确保返回完整的实体和关系数据
            result = {
                "sentences_processed": len(sentences),
                "paragraphs_processed": len(paragraphs),
                "entities_created": entities_created,
                "relations_created": relations_created,
                "entities": all_entities,
                "relations": all_relations
            }

            # 添加调试日志，查看all_entities和all_relations的实际内容
            logger.debug(f"all_entities 内容: {all_entities}")
            logger.debug(f"all_relations 内容: {all_relations}")
            logger.info(f"文本处理完成: {result}")
            return result

        except Exception as e:
            logger.error(f"文本处理失败: {e}")
            raise

    def _extract_entities_and_relations(self, sentence: str) -> Dict[str, Any]:
        """
        使用 LLM 从句子中提取实体和关系

        Args:
            sentence: 输入句子

        Returns:
            提取结果 {"entities": [...], "relations": [...]}
        """
        # 构建提示词
        prompt = f"""
请从以下医学文本中提取实体和关系。

实体类型包括：
{', '.join(self.entity_types)}

关系类型包括：
{', '.join(self.relation_types)}

文本：
{sentence}

请以JSON格式返回结果：
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "description": "描述"}}
    ],
    "relations": [
        {{"subject": "主体实体", "predicate": "关系类型", "object": "客体实体"}}
    ]
}}

注意：
1. 提取所有相关的医学实体
2. 确保关系的主体和客体都在实体列表中
3. 如果文本中没有明确的实体或关系，返回空列表
"""

        try:
            # 调用 LLM
            messages = [
                {"role": "system", "content": "你是一个医学知识图谱构建助手，擅长从医学文本中提取实体和关系。"},
                {"role": "user", "content": prompt}
            ]

            response = self.llm.chat(messages, temperature=0.3)
            logger.debug(f"LLM原始响应: {response}")

            # 确保导入json和re模块
            import json
            import re

            # 改进的JSON提取逻辑
            try:
                # 尝试直接解析整个响应
                result = json.loads(response)
            except json.JSONDecodeError:
                # 如果失败，尝试提取JSON部分
                # 使用更严格的正则表达式，只匹配最外层的JSON对象
                json_pattern = r'\{[\s\S]*?\}'
                matches = re.findall(json_pattern, response)
                
                if matches:
                    # 尝试解析每个匹配项，直到找到有效的JSON
                    for match in matches:
                        try:
                            result = json.loads(match)
                            logger.debug(f"成功解析JSON: {match[:100]}...")
                            break
                        except json.JSONDecodeError:
                            continue
                    else:
                        # 所有匹配项都无法解析
                        logger.warning(f"LLM响应无法解析为JSON: {response[:150]}...")
                        result = {"entities": [], "relations": []}
                else:
                    logger.warning(f"LLM响应中没有找到JSON: {response[:150]}...")
                    result = {"entities": [], "relations": []}

            return result

        except Exception as e:
            logger.error(f"实体关系提取失败: {e}")
            return {"entities": [], "relations": []}

    def _create_entity(self, entity: Dict[str, str]):
        """
        在图数据库中创建实体节点

        Args:
            entity: 实体信息 {"name": "...", "type": "...", "description": "..."}
        """
        name = entity.get("name", "").strip()
        entity_type = entity.get("type", "").strip()
        description = entity.get("description", "").strip()

        if not name or not entity_type:
            return

        # 检查实体类型是否有效
        if entity_type not in self.entity_types:
            logger.warning(f"未知的实体类型: {entity_type}")
            entity_type = "Disease"  # 默认为疾病

        # 创建或更新节点
        # 确保 entity_type 是有效的标签（Neo4j 标签不能包含特殊字符）
        # 清理 entity_type，只保留字母和数字
        import re
        clean_entity_type = re.sub(r'[^a-zA-Z0-9_]', '', entity_type)
        if not clean_entity_type:
            clean_entity_type = "Entity"  # 如果清理后为空，使用默认标签
        
        query = f"""
        MERGE (e:{clean_entity_type} {{name: $name}})
        ON CREATE SET e.description = $description, e.type = $entity_type, e.created_at = datetime()
        ON MATCH SET e.description = COALESCE($description, e.description), e.type = $entity_type, e.updated_at = datetime()
        RETURN e
        """

        self.neo4j.execute_write(
            query,
            {"name": name, "description": description, "entity_type": entity_type}
        )

        logger.debug(f"创建/更新实体: {clean_entity_type} (原始类型: {entity_type}) - {name}")

    def _create_relation(self, relation: Dict[str, str]):
        """
        在图数据库中创建关系

        Args:
            relation: 关系信息 {"subject": "...", "predicate": "...", "object": "..."}
        """
        subject = relation.get("subject", "").strip()
        predicate = relation.get("predicate", "").strip()
        obj = relation.get("object", "").strip()

        if not subject or not predicate or not obj:
            return

        # 检查关系类型是否有效
        if predicate not in self.relation_types:
            logger.warning(f"未知的关系类型: {predicate}")
            predicate = "ASSOCIATED_WITH"  # 默认关系

        # 创建关系
        query = f"""
        MATCH (a), (b)
        WHERE a.name = $subject AND b.name = $object
        MERGE (a)-[r:{predicate}]->(b)
        ON CREATE SET r.created_at = datetime()
        RETURN r
        """

        try:
            self.neo4j.execute_write(
                query,
                {"subject": subject, "object": obj}
            )
            logger.debug(f"创建关系: {subject} -{predicate}-> {obj}")
        except Exception as e:
            logger.warning(f"关系创建失败: {e}")

    def batch_import(self, documents: List[str]) -> Dict[str, Any]:
        """
        批量导入文档

        Args:
            documents: 文档列表

        Returns:
            导入统计
        """
        total_stats = {
            "documents_processed": 0,
            "sentences_processed": 0,
            "entities_created": 0,
            "relations_created": 0
        }

        for i, doc in enumerate(documents):
            logger.info(f"处理文档 {i + 1}/{len(documents)}")
            try:
                stats = self.process_text(doc)
                total_stats["documents_processed"] += 1
                total_stats["sentences_processed"] += stats.get("sentences_processed", 0)
                total_stats["entities_created"] += stats.get("entities_created", 0)
                total_stats["relations_created"] += stats.get("relations_created", 0)
            except Exception as e:
                logger.error(f"文档 {i + 1} 处理失败: {e}")

        logger.info(f"批量导入完成: {total_stats}")
        return total_stats


# 别名，兼容旧代码
KGBuilder = KnowledgeGraphBuilder

# 示例用法
if __name__ == "__main__":
    import logging
    from db.neo4j_client import Neo4jClient
    from llm.client import LLMClient

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("知识图谱构建器测试")
    print("=" * 60)

    # 创建客户端
    with Neo4jClient() as neo4j_client, LLMClient() as llm_client:
        # 创建构建器
        builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client
        )

        # 测试文本
        test_text = """
        重症急性胰腺炎是一种严重的胰腺炎症。
        患者会出现剧烈腹痛和发热。
        治疗方法包括禁食禁水和静脉营养支持。
        """

        # 处理文本
        result = builder.process_text(test_text)
        print(f"\n处理结果: {result}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
