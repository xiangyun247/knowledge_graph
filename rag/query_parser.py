"""
查询解析器
解析用户查询，提取关键信息：实体、意图、关键词
使用 LLM 进行智能解析
"""

import config
from config import resolve_entity_type
from typing import Dict, Any, List, Optional
import logging
import json
import re
from llm.client import LLMClient

logger = logging.getLogger(__name__)


class QueryParser:
    """查询解析器"""

    def __init__(self, llm_client: LLMClient):
        """
        初始化查询解析器

        Args:
            llm_client: LLM 客户端实例
        """
        self.llm = llm_client
        self.entity_types = config.ENTITY_TYPES
        self.relation_types = config.RELATION_TYPES

        # 查询意图类型（与表3 关系类型对应）
        self.intent_types = [
            "definition",  # 定义/概念查询：什么是X？
            "symptom",  # 症状查询：有哪些症状？
            "treatment",  # 治疗查询：如何治疗？
            "cause",  # 病因查询：为什么会X？
            "diagnosis",  # 诊断/检查查询：如何诊断？需要做哪些检查？
            "prevention",  # 预防查询：如何预防？
            "complication",  # 并发症查询：会引起什么？
            "prognosis",  # 预后查询：预后如何？
            "population",  # 多发人群：哪些人容易得？
            "department",  # 就诊科室：挂什么科？
            "comparison",  # 比较/鉴别诊断：X和Y有什么区别？
            "other"  # 其他
        ]

        logger.info("查询解析器初始化完成")

    def parse(self, query: str) -> Dict[str, Any]:
        """
        解析查询

        Args:
            query: 用户查询文本

        Returns:
            解析结果字典:
            {
                "original_query": str,      # 原始查询
                "normalized_query": str,    # 标准化查询
                "entities": List[Dict],     # 识别的实体
                "intent": str,              # 查询意图
                "keywords": List[str],      # 关键词
                "question_type": str,       # 问题类型
                "confidence": float         # 置信度
            }
        """
        logger.info(f"开始解析查询: {query}")

        try:
            # 1. 文本预处理
            normalized_query = self._normalize_query(query)

            # 2. 使用 LLM 进行深度解析
            llm_result = self._parse_with_llm(normalized_query)

            # 3. 基于规则的补充解析
            rule_result = self._parse_with_rules(normalized_query)

            # 4. 合并结果
            result = self._merge_parse_results(
                query,
                normalized_query,
                llm_result,
                rule_result
            )

            logger.info(f"查询解析完成: 实体={len(result['entities'])}, 意图={result['intent']}")
            logger.debug(f"解析结果: {result}")

            return result

        except Exception as e:
            logger.error(f"查询解析失败: {e}")
            import traceback
            traceback.print_exc()

            # 返回基础解析结果
            return {
                "original_query": query,
                "normalized_query": query,
                "entities": [],
                "intent": "other",
                "keywords": self._extract_keywords(query),
                "question_type": "unknown",
                "confidence": 0.3
            }

    def _normalize_query(self, query: str) -> str:
        """
        标准化查询文本

        Args:
            query: 原始查询

        Returns:
            标准化后的查询
        """
        # 去除多余空白
        query = " ".join(query.split())

        # 统一标点符号
        query = query.replace("？", "?").replace("！", "!")
        query = query.replace("，", ",").replace("。", ".")

        # 去除特殊字符
        query = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\?\!,\.]', '', query)

        return query.strip()

    def _parse_with_llm(self, query: str) -> Dict[str, Any]:
        """
        使用 LLM 解析查询

        Args:
            query: 查询文本

        Returns:
            LLM 解析结果
        """
        # 构建提示词
        prompt = f"""
请分析以下医学问题，提取关键信息。

问题：{query}

实体类型包括：{', '.join(self.entity_types)}
查询意图包括：{', '.join(self.intent_types)}

请以JSON格式返回结果：
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "confidence": 0.9}}
    ],
    "intent": "查询意图",
    "keywords": ["关键词1", "关键词2"],
    "question_type": "问题类型（what/how/why/which等）",
    "explanation": "简短解释"
}}

要求：
1. 识别所有医学相关实体（疾病、症状、治疗、药物等）
2. 判断用户的查询意图
3. 提取关键词（2-5个）
4. 置信度范围 0.0-1.0
5. 如果无法识别，相应字段返回空列表或 "unknown"
"""

        try:
            # 调用 LLM
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的医学问答系统，擅长分析和理解医学相关问题。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            response = self.llm.chat(messages, temperature=0.3)

            # 解析 JSON 响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.debug(f"LLM 解析结果: {result}")
                return result
            else:
                logger.warning(f"LLM 响应无法解析为 JSON: {response[:200]}")
                return {}

        except Exception as e:
            logger.error(f"LLM 解析失败: {e}")
            return {}

    def _parse_with_rules(self, query: str) -> Dict[str, Any]:
        """
        基于规则的解析（备用方案）

        Args:
            query: 查询文本

        Returns:
            规则解析结果
        """
        result = {
            "entities": [],
            "intent": "other",
            "keywords": [],
            "question_type": "unknown"
        }

        # 1. 识别问题类型
        result["question_type"] = self._identify_question_type(query)

        # 2. 识别意图
        result["intent"] = self._identify_intent(query)

        # 3. 提取关键词
        result["keywords"] = self._extract_keywords(query)

        # 4. 简单实体识别（基于关键词匹配）
        result["entities"] = self._extract_entities_by_keywords(query)

        return result

    def _identify_question_type(self, query: str) -> str:
        """识别问题类型"""
        query_lower = query.lower()

        if any(word in query_lower for word in ["什么是", "什么叫", "啥是", "what is", "what are"]):
            return "what"
        elif any(word in query_lower for word in ["如何", "怎么", "怎样", "how to", "how can"]):
            return "how"
        elif any(word in query_lower for word in ["为什么", "为啥", "why", "原因"]):
            return "why"
        elif any(word in query_lower for word in ["哪个", "哪些", "which", "what"]):
            return "which"
        elif any(word in query_lower for word in ["是否", "有没有", "会不会", "is", "are", "can"]):
            return "yes_no"
        else:
            return "other"

    def _identify_intent(self, query: str) -> str:
        """识别查询意图"""
        query_lower = query.lower()

        # 定义意图关键词（覆盖新关系类型对应的查询）
        intent_keywords = {
            "definition": ["什么是", "定义", "概念", "是指"],
            "symptom": ["症状", "表现", "特征", "感觉", "体征"],
            "treatment": ["治疗", "处理", "用药", "疗法", "手术"],
            "cause": ["原因", "为什么", "导致", "引起", "病因"],
            "diagnosis": ["诊断", "检查", "判断", "确诊", "需要做哪些检查"],
            "prevention": ["预防", "避免", "防止"],
            "complication": ["并发症", "后果", "影响", "危害"],
            "prognosis": ["预后", "恢复", "治愈", "能好吗"],
            "population": ["多发", "人群", "哪些人", "好发于", "儿童", "老年"],
            "department": ["科室", "挂号", "看什么科", "就诊"],
            "comparison": ["区别", "对比", "不同", "比较", "鉴别"],
        }

        # 匹配意图
        for intent, keywords in intent_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent

        return "other"

    def _extract_keywords(self, query: str) -> List[str]:
        """
        提取关键词（简单实现）

        Args:
            query: 查询文本

        Returns:
            关键词列表
        """
        # 移除停用词
        stopwords = {
            "的", "是", "在", "有", "和", "了", "吗", "呢", "啊", "吧",
            "什么", "如何", "怎么", "怎样", "为什么", "哪些", "哪个",
            "一个", "这个", "那个", "可以", "能够", "需要"
        }

        # 提取中文词汇（2-4个字）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', query)

        # 过滤停用词
        keywords = [w for w in words if w not in stopwords]

        # 去重并返回
        return list(dict.fromkeys(keywords))[:5]  # 最多返回5个

    def _extract_entities_by_keywords(self, query: str) -> List[Dict[str, Any]]:
        """
        基于关键词的简单实体识别（支持新实体类型）
        """
        entities = []

        # 实体类型关键词映射（表2 实体描述框架）
        type_keywords = {
            "Disease": ["炎", "症", "病", "癌", "瘤", "疾", "综合征"],
            "Symptom": ["痛", "疼", "热", "肿", "吐", "泻", "晕", "咳", "红", "痒"],
            "Medicine": ["药", "素", "灵", "林", "西林", "激素", "片", "胶囊"],
            "Population": ["儿童", "成人", "老年", "孕妇", "群体"],
            "Department": ["科", "病房", "门诊", "内科", "外科"],
            "Hospital": ["医院", "中心", "研究所"],
            "PhysicalExamination": ["呼吸", "心率", "血压", "体温"],
            "LaboratoryExamination": ["血", "尿", "便", "常规", "生化"],
            "ImagingExamination": ["CT", "MRI", "超声", "X", "影像"],
            "AnatomicalSite": ["腹部", "颈部", "心脏", "胰腺", "肝", "肾"],
            "TCMTreatment": ["清热", "活血", "化瘀", "解毒", "中医"],
            "Surgery": ["手术", "介入", "切除"],
            "DrugTreatment": ["治疗", "用药", "输液"],
            "Prognosis": ["预后", "良好", "随访"],
        }

        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,8}', query)

        for word in words:
            entity_type = None
            for etype, kws in type_keywords.items():
                if any(kw in word for kw in kws) and etype in self.entity_types:
                    entity_type = etype
                    break
            if not entity_type and any(kw in word for kw in ["治疗", "手术", "疗法", "护理"]):
                entity_type = "DrugTreatment" if "DrugTreatment" in self.entity_types else "OtherTreatment"
            if entity_type:
                entities.append({
                    "name": word,
                    "type": resolve_entity_type(entity_type),
                    "confidence": 0.6,
                })

        return entities

    def _merge_parse_results(
            self,
            original_query: str,
            normalized_query: str,
            llm_result: Dict[str, Any],
            rule_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并 LLM 和规则解析结果

        Args:
            original_query: 原始查询
            normalized_query: 标准化查询
            llm_result: LLM 解析结果
            rule_result: 规则解析结果

        Returns:
            合并后的结果
        """
        # 优先使用 LLM 结果，规则结果作为备用
        merged = {
            "original_query": original_query,
            "normalized_query": normalized_query,
            "entities": llm_result.get("entities") or rule_result.get("entities", []),
            "intent": llm_result.get("intent") or rule_result.get("intent", "other"),
            "keywords": llm_result.get("keywords") or rule_result.get("keywords", []),
            "question_type": llm_result.get("question_type") or rule_result.get("question_type", "unknown"),
            "confidence": self._calculate_confidence(llm_result, rule_result)
        }

        # 实体类型规范化（中文→英文）并去重
        for e in merged["entities"]:
            if isinstance(e, dict) and e.get("type"):
                e["type"] = resolve_entity_type(e["type"])
        merged["entities"] = self._deduplicate_entities(merged["entities"])

        # 去重关键词
        merged["keywords"] = list(dict.fromkeys(merged["keywords"]))

        return merged

    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        实体去重

        Args:
            entities: 实体列表

        Returns:
            去重后的实体列表
        """
        unique_entities = {}

        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue

            # 如果已存在，保留置信度更高的
            # 确保 type 在配置中
            etype = entity.get("type", "")
            if etype and etype not in self.entity_types:
                entity = {**entity, "type": resolve_entity_type(etype)}
            if name in unique_entities:
                if entity.get("confidence", 0) > unique_entities[name].get("confidence", 0):
                    unique_entities[name] = entity
            else:
                unique_entities[name] = entity

        return list(unique_entities.values())

    def _calculate_confidence(
            self,
            llm_result: Dict[str, Any],
            rule_result: Dict[str, Any]
    ) -> float:
        """
        计算整体置信度

        Args:
            llm_result: LLM 结果
            rule_result: 规则结果

        Returns:
            置信度分数 (0.0-1.0)
        """
        # 如果 LLM 有结果，基础置信度较高
        if llm_result.get("entities") or llm_result.get("intent"):
            base_confidence = 0.8
        else:
            base_confidence = 0.5

        # 根据实体数量调整
        entity_count = len(llm_result.get("entities", []))
        if entity_count > 0:
            base_confidence += 0.1

        # 根据意图明确性调整
        if llm_result.get("intent") and llm_result["intent"] != "other":
            base_confidence += 0.1

        # 限制在 0.0-1.0 范围
        return min(1.0, base_confidence)

    def extract_entity_names(self, parsed_result: Dict[str, Any]) -> List[str]:
        """
        从解析结果中提取实体名称列表

        Args:
            parsed_result: 解析结果

        Returns:
            实体名称列表
        """
        entities = parsed_result.get("entities", [])
        return [entity["name"] for entity in entities if entity.get("name")]


# 示例用法
if __name__ == "__main__":
    import logging
    from llm.client import LLMClient

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("查询解析器测试")
    print("=" * 60)

    # 创建 LLM 客户端
    llm_client = LLMClient()

    if not llm_client.verify_connection():
        print("❌ LLM 连接失败")
        exit(1)

    # 创建解析器
    parser = QueryParser(llm_client)

    # 测试查询
    test_queries = [
        "什么是重症急性胰腺炎？",
        "胰腺炎有哪些症状？",
        "如何治疗急性胰腺炎？",
        "为什么会得胰腺炎？",
        "胰腺炎需要做哪些检查？"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 60)

        result = parser.parse(query)

        print(f"意图: {result['intent']}")
        print(f"问题类型: {result['question_type']}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"实体: {[e['name'] for e in result['entities']]}")
        print(f"关键词: {result['keywords']}")

    # 关闭客户端
    llm_client.close()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
