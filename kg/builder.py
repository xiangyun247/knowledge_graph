"""
知识图谱构建器
从文本中提取实体和关系，构建知识图谱
"""

import config
from config import (
    resolve_entity_type,
    resolve_relation_type,
    ENTITY_NAME_MIN_LEN,
    ENTITY_NAME_BLACKLIST,
    RELATION_SEMANTICS,
)
from typing import List, Dict, Any, Optional
import logging
import re
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
                # 后处理：实体名规范化、类型校验、关系与实体一致性（建议4）
                extraction_result = self._validate_and_normalize_extraction(extraction_result)

                # 质量统计日志（有丢弃时输出）
                vstats = extraction_result.get("validation_stats") or {}
                if any(vstats.get(k, 0) > 0 for k in ("entities_skipped_invalid", "entities_skipped_duplicate",
                                                      "relations_skipped_subject_missing", "relations_skipped_object_missing",
                                                      "relations_skipped_self_loop", "relations_skipped_duplicate", "relations_type_mapped")):
                    logger.info("段落 %d 后处理统计: %s", i + 1, vstats)

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

    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        """
        实体名规范化：strip、全角转半角、多余空格合并。
        便于同义合并（如「轻度 认知障碍」与「轻度认知障碍」视为同一实体）。
        """
        if not name or not isinstance(name, str):
            return ""
        s = name.strip()
        # 全角转半角（数字、字母、空格）
        out = []
        for c in s:
            if c == "\u3000":
                out.append(" ")
            elif "\uff01" <= c <= "\uff5e":
                out.append(chr(ord(c) - 0xfee0))
            elif "\uff10" <= c <= "\uff19":
                out.append(chr(ord(c) - 0xfee0))
            else:
                out.append(c)
        s = "".join(out)
        # 合并多余空格
        return " ".join(s.split())

    @staticmethod
    def _is_valid_entity_name(name: str) -> bool:
        """
        校验实体名是否有效：长度、黑名单、纯数字。
        返回 False 时该实体应被过滤。
        """
        if not name or len(name) < ENTITY_NAME_MIN_LEN:
            return False
        if name in ENTITY_NAME_BLACKLIST:
            return False
        # 纯数字或纯符号
        if re.match(r"^[\d\s\.\-]+$", name):
            return False
        return True

    def _validate_and_normalize_extraction(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        后处理校验与规范化（见 docs/OPTIMIZATION_SUGGESTIONS.md 建议4）：
        - 实体名规范化、同义合并、过滤无效实体名
        - 实体类型/关系类型校验并映射到合法值
        - 关系与实体一致性：subject/object 必须在 entities 中
        - 自环过滤、重复去重、关系语义软校验
        """
        if not isinstance(result, dict):
            return {"entities": [], "relations": [], "validation_stats": {}}
        entities_in = result.get("entities") or []
        relations_in = result.get("relations") or []
        if not isinstance(entities_in, list):
            entities_in = []
        if not isinstance(relations_in, list):
            relations_in = []

        stats = {
            "entities_skipped_invalid": 0,
            "entities_skipped_duplicate": 0,
            "relations_skipped_subject_missing": 0,
            "relations_skipped_object_missing": 0,
            "relations_skipped_self_loop": 0,
            "relations_skipped_duplicate": 0,
            "relations_type_mapped": 0,
            "relations_semantic_warn": 0,
        }

        # 1. 实体名规范化、同义合并、过滤无效实体名
        entities_out: List[Dict[str, Any]] = []
        name_to_entity: Dict[str, Dict[str, Any]] = {}
        for e in entities_in:
            if not isinstance(e, dict):
                continue
            raw_name = (e.get("name") or "").strip()
            name = self._normalize_entity_name(raw_name)
            if not name:
                continue
            if not self._is_valid_entity_name(name):
                stats["entities_skipped_invalid"] += 1
                logger.debug("实体名无效（过短/黑名单/纯数字），跳过: %s", name)
                continue
            if name in name_to_entity:
                stats["entities_skipped_duplicate"] += 1
                logger.debug("同义实体合并: 原始=%s, 规范名=%s", raw_name, name)
                continue
            raw_type = (e.get("type") or "").strip()
            entity_type = resolve_entity_type(raw_type)
            if entity_type not in self.entity_types:
                logger.warning("实体类型不在配置中，映射为 Disease: name=%s, type=%s", name, raw_type)
                entity_type = "Disease"
            entity_out = {
                "name": name,
                "type": entity_type,
                "description": (e.get("description") or "").strip() or name,
            }
            name_to_entity[name] = entity_out
            entities_out.append(entity_out)

        valid_names = set(name_to_entity.keys())
        name_to_type = {e["name"]: e["type"] for e in entities_out}

        # 2. 关系：subject/object 必须在实体集中；自环过滤；重复去重；predicate 校验；语义软校验
        default_relation = "BELONGS_TO"
        relations_out: List[Dict[str, str]] = []
        seen_relations: set = set()
        for r in relations_in:
            if not isinstance(r, dict):
                continue
            sub = self._normalize_entity_name(r.get("subject") or "")
            obj = self._normalize_entity_name(r.get("object") or "")
            raw_pred = (r.get("predicate") or "").strip()
            pred = resolve_relation_type(raw_pred)
            if not sub or not obj:
                logger.debug("关系缺少 subject 或 object，丢弃: %s", r)
                continue
            if sub not in valid_names:
                stats["relations_skipped_subject_missing"] += 1
                logger.info("关系 subject 不在实体列表中，丢弃该关系: subject=%s, object=%s, predicate=%s", sub, obj, pred)
                continue
            if obj not in valid_names:
                stats["relations_skipped_object_missing"] += 1
                logger.info("关系 object 不在实体列表中，丢弃该关系: subject=%s, object=%s, predicate=%s", sub, obj, pred)
                continue
            if sub == obj:
                stats["relations_skipped_self_loop"] += 1
                logger.debug("关系自环，丢弃: %s -[%s]-> %s", sub, pred, obj)
                continue
            rel_key = (sub, pred, obj)
            if rel_key in seen_relations:
                stats["relations_skipped_duplicate"] += 1
                logger.debug("关系重复，丢弃: %s", rel_key)
                continue
            if pred not in self.relation_types:
                logger.warning("关系类型不在配置中，映射为 %s: predicate=%s", default_relation, raw_pred)
                pred = default_relation
                stats["relations_type_mapped"] += 1
            # 语义软校验：不匹配时打日志，不丢弃
            if pred in RELATION_SEMANTICS:
                sub_types, obj_types = RELATION_SEMANTICS[pred]
                sub_type = name_to_type.get(sub, "")
                obj_type = name_to_type.get(obj, "")
                mismatch = False
                if sub_types and sub_type not in sub_types:
                    mismatch = True
                    logger.debug("关系语义提示: %s 的 subject 类型 %s 不在预期 %s 中: %s", pred, sub_type, sub_types, sub)
                if obj_types and obj_type not in obj_types:
                    mismatch = True
                    logger.debug("关系语义提示: %s 的 object 类型 %s 不在预期 %s 中: %s", pred, obj_type, obj_types, obj)
                if mismatch:
                    stats["relations_semantic_warn"] += 1
            seen_relations.add(rel_key)
            relations_out.append({"subject": sub, "predicate": pred, "object": obj})

        return {"entities": entities_out, "relations": relations_out, "validation_stats": stats}

    def _build_entity_type_groups(self) -> str:
        """按类别分组构建实体类型描述，便于 LLM 理解与选择"""
        groups = [
            "【基础】Disease(疾病), Symptom(症状或体征), Population(群体), Medicine(药物), Prognosis(预后)",
            "【检查检验】PhysicalExamination(体格检查), LaboratoryExamination(实验室检查), ImagingExamination(影像学检查), PathologyExamination(病理检查), OtherExamination(其它检查), AbnormalExaminationResult(异常检查结果)",
            "【治疗】TCMTreatment(中医治疗), Surgery(手术), DrugTreatment(药物治疗), WesternPhysicalTherapy(西医理疗), OtherTreatment(其它治疗)",
            "【解剖】AnatomicalSite(解剖部位), AnatomicalSubstance(解剖物质)",
            "【设备】MedicalEquipment(医用设备、器械和材料)",
            "【机构】Hospital(医院), Department(科室)",
            "【病因类】Gene(基因), Microorganism(微生物类), PhysicalChemicalFactor(理化因素), PsychologicalBehavior(心理行为), Lifestyle(生活习惯), ImmuneFactor(免疫因素), DisuseFactor(废用性因素)",
            "【语义】ICD10Code(ICD10编码), Synonym(同义词)",
        ]
        return "\n".join(groups)

    def _build_relation_type_groups(self) -> str:
        """按类别分组构建关系类型描述，便于 LLM 理解与选择"""
        groups = [
            "【疾病-检查】HAS_ABNORMAL_EXAM_RESULT(疾病-异常检查结果), EXAM_HAS_ABNORMAL_RESULT(检查-异常结果), REQUIRES_EXAM(用于检查)",
            "【疾病/症状-治疗/药物】TREATED_BY(用于治疗), PREVENTED_BY(用于预防)",
            "【治疗-疾病】TREATS_COMPLICATION(治疗并发症)",
            "【药物-疾病/症状】HAS_SIDE_EFFECT(副作用)",
            "【疾病-症状/群体/解剖/预后】HAS_SYMPTOM(症状或体征), AFFECTS_POPULATION(多发人群), AFFECTS_SITE(发病部位), HAS_PROGNOSIS(预后)",
            "【疾病-疾病】HAS_COMPLICATION(并发症), DIFFERENTIAL_DIAGNOSIS(鉴别诊断)",
            "【疾病-病因】HAS_ETIOLOGY(病因)",
            "【疾病-机构】BELONGS_TO_DEPARTMENT(就诊科室), TREATED_AT_HOSPITAL(就诊医院)",
            "【检查/治疗-设备】USES_EQUIPMENT(使用于)",
            "【通用/语义】BELONGS_TO(属于), HAS_ICD10_CODE(ICD10编码), HAS_SYNONYM(别称)",
        ]
        return "\n".join(groups)

    def _extract_entities_and_relations(self, sentence: str) -> Dict[str, Any]:
        """
        使用 LLM 从句子中提取实体和关系

        Args:
            sentence: 输入句子

        Returns:
            提取结果 {"entities": [...], "relations": [...]}
        """
        # 构建提示词：按类别分组描述 + Few-shot 示例（覆盖新类型）
        entity_groups = self._build_entity_type_groups()
        relation_groups = self._build_relation_type_groups()

        prompt = f"""
请从以下医学文本中提取实体和关系。

【实体类型】按类别分组，请严格使用下列类型名：
{entity_groups}

【关系类型】按类别分组，请严格使用下列类型名：
{relation_groups}

【输出格式约束】
- 只输出一个 JSON 对象，包含且仅包含 "entities" 和 "relations" 两个 key。
- relations 中的 subject 和 object 必须是 entities 中某一项的 name，不得新增未列出的实体。
- 若某句无实体或关系，对应列表可为空，但必须保留 entities 和 relations 两个 key。

【示例 1】
输入文本：急性胰腺炎患者常出现腹痛、恶心呕吐。该病可采用禁食、补液等治疗，并需进行血淀粉酶检查。
输出：
{{
  "entities": [
    {{"name": "急性胰腺炎", "type": "Disease", "description": "疾病"}},
    {{"name": "腹痛", "type": "Symptom", "description": "症状"}},
    {{"name": "恶心呕吐", "type": "Symptom", "description": "症状"}},
    {{"name": "禁食", "type": "DrugTreatment", "description": "治疗方式"}},
    {{"name": "补液", "type": "DrugTreatment", "description": "治疗方式"}},
    {{"name": "血淀粉酶检查", "type": "LaboratoryExamination", "description": "实验室检查"}}
  ],
  "relations": [
    {{"subject": "急性胰腺炎", "predicate": "HAS_SYMPTOM", "object": "腹痛"}},
    {{"subject": "急性胰腺炎", "predicate": "HAS_SYMPTOM", "object": "恶心呕吐"}},
    {{"subject": "急性胰腺炎", "predicate": "TREATED_BY", "object": "禁食"}},
    {{"subject": "急性胰腺炎", "predicate": "TREATED_BY", "object": "补液"}},
    {{"subject": "急性胰腺炎", "predicate": "REQUIRES_EXAM", "object": "血淀粉酶检查"}}
  ]
}}

【示例 2】
输入文本：川崎病多发于儿童，常见于5岁以下儿童。血沉增快、ST段改变是常见异常检查结果。可予阿司匹林抗炎，并需超声心动图检查。预后良好。
输出：
{{
  "entities": [
    {{"name": "川崎病", "type": "Disease", "description": "疾病"}},
    {{"name": "儿童", "type": "Population", "description": "群体"}},
    {{"name": "血沉增快", "type": "AbnormalExaminationResult", "description": "异常检查结果"}},
    {{"name": "ST段改变", "type": "AbnormalExaminationResult", "description": "异常检查结果"}},
    {{"name": "阿司匹林", "type": "Medicine", "description": "药物"}},
    {{"name": "超声心动图", "type": "ImagingExamination", "description": "影像学检查"}},
    {{"name": "良好", "type": "Prognosis", "description": "预后"}}
  ],
  "relations": [
    {{"subject": "川崎病", "predicate": "AFFECTS_POPULATION", "object": "儿童"}},
    {{"subject": "川崎病", "predicate": "HAS_ABNORMAL_EXAM_RESULT", "object": "血沉增快"}},
    {{"subject": "川崎病", "predicate": "HAS_ABNORMAL_EXAM_RESULT", "object": "ST段改变"}},
    {{"subject": "川崎病", "predicate": "TREATED_BY", "object": "阿司匹林"}},
    {{"subject": "川崎病", "predicate": "REQUIRES_EXAM", "object": "超声心动图"}},
    {{"subject": "川崎病", "predicate": "HAS_PROGNOSIS", "object": "良好"}}
  ]
}}

【示例 3】
输入文本：急性胰腺炎可并发假性囊肿、胰腺坏死。需与消化性溃疡穿孔鉴别。发病部位在腹部。可就诊于消化内科或普外科。
输出：
{{
  "entities": [
    {{"name": "急性胰腺炎", "type": "Disease", "description": "疾病"}},
    {{"name": "假性囊肿", "type": "Disease", "description": "并发症"}},
    {{"name": "胰腺坏死", "type": "Disease", "description": "并发症"}},
    {{"name": "消化性溃疡穿孔", "type": "Disease", "description": "鉴别疾病"}},
    {{"name": "腹部", "type": "AnatomicalSite", "description": "解剖部位"}},
    {{"name": "消化内科", "type": "Department", "description": "科室"}},
    {{"name": "普外科", "type": "Department", "description": "科室"}}
  ],
  "relations": [
    {{"subject": "急性胰腺炎", "predicate": "HAS_COMPLICATION", "object": "假性囊肿"}},
    {{"subject": "急性胰腺炎", "predicate": "HAS_COMPLICATION", "object": "胰腺坏死"}},
    {{"subject": "急性胰腺炎", "predicate": "DIFFERENTIAL_DIAGNOSIS", "object": "消化性溃疡穿孔"}},
    {{"subject": "急性胰腺炎", "predicate": "AFFECTS_SITE", "object": "腹部"}},
    {{"subject": "急性胰腺炎", "predicate": "BELONGS_TO_DEPARTMENT", "object": "消化内科"}},
    {{"subject": "急性胰腺炎", "predicate": "BELONGS_TO_DEPARTMENT", "object": "普外科"}}
  ]
}}

【示例 4】
输入文本：长期熬夜、饮水量少可能导致胰腺炎。腺病毒可诱发川崎病。糖皮质激素可导致急性肾损伤、消化不良等副作用。
输出：
{{
  "entities": [
    {{"name": "熬夜", "type": "Lifestyle", "description": "生活习惯"}},
    {{"name": "饮水量少", "type": "Lifestyle", "description": "生活习惯"}},
    {{"name": "胰腺炎", "type": "Disease", "description": "疾病"}},
    {{"name": "腺病毒", "type": "Microorganism", "description": "微生物"}},
    {{"name": "川崎病", "type": "Disease", "description": "疾病"}},
    {{"name": "糖皮质激素", "type": "Medicine", "description": "药物"}},
    {{"name": "急性肾损伤", "type": "Disease", "description": "副作用"}},
    {{"name": "消化不良", "type": "Symptom", "description": "副作用"}}
  ],
  "relations": [
    {{"subject": "熬夜", "predicate": "HAS_ETIOLOGY", "object": "胰腺炎"}},
    {{"subject": "饮水量少", "predicate": "HAS_ETIOLOGY", "object": "胰腺炎"}},
    {{"subject": "腺病毒", "predicate": "HAS_ETIOLOGY", "object": "川崎病"}},
    {{"subject": "糖皮质激素", "predicate": "HAS_SIDE_EFFECT", "object": "急性肾损伤"}},
    {{"subject": "糖皮质激素", "predicate": "HAS_SIDE_EFFECT", "object": "消化不良"}}
  ]
}}

【示例 5】
输入文本：轻度认知障碍老人日常需注意记忆减退与定向力下降，应按时服药、防跌倒防走失，复诊前带齐病历与用药清单。
输出：
{{
  "entities": [
    {{"name": "轻度认知障碍", "type": "Disease", "description": "疾病"}},
    {{"name": "记忆减退", "type": "Symptom", "description": "症状"}},
    {{"name": "定向力下降", "type": "Symptom", "description": "症状"}},
    {{"name": "服药", "type": "Lifestyle", "description": "照护行为"}},
    {{"name": "防跌倒", "type": "Lifestyle", "description": "照护要点"}},
    {{"name": "防走失", "type": "Lifestyle", "description": "照护要点"}},
    {{"name": "复诊", "type": "Lifestyle", "description": "照护行为"}},
    {{"name": "病历", "type": "Other", "description": "资料"}},
    {{"name": "用药清单", "type": "Other", "description": "资料"}}
  ],
  "relations": [
    {{"subject": "轻度认知障碍", "predicate": "HAS_SYMPTOM", "object": "记忆减退"}},
    {{"subject": "轻度认知障碍", "predicate": "HAS_SYMPTOM", "object": "定向力下降"}},
    {{"subject": "轻度认知障碍", "predicate": "TREATED_BY", "object": "服药"}},
    {{"subject": "轻度认知障碍", "predicate": "TREATED_BY", "object": "防跌倒"}},
    {{"subject": "轻度认知障碍", "predicate": "TREATED_BY", "object": "防走失"}},
    {{"subject": "复诊", "predicate": "REQUIRES_EXAM", "object": "病历"}},
    {{"subject": "复诊", "predicate": "REQUIRES_EXAM", "object": "用药清单"}}
  ]
}}

【示例 6】
输入文本：患者今日一般情况可。
输出：
{{"entities": [], "relations": []}}

【待提取文本】
{sentence}

请仅输出上述格式的 JSON，不要输出其他说明。
"""

        try:
            # 调用 LLM
            messages = [
                {"role": "system", "content": "你是一个医学知识图谱构建助手，擅长从医学文本中提取实体和关系。"},
                {"role": "user", "content": prompt}
            ]

            response = self.llm.chat(messages, temperature=0, max_tokens=4096)
            logger.debug(f"LLM原始响应: {response}")

            import json
            import re

            def extract_json(text: str) -> dict:
                """从 LLM 响应中提取最外层 JSON，支持 ```json 代码块、截断 JSON、字符串内换行。"""
                text = (text or "").strip()
                # 1. 去掉 markdown 代码块（无闭合 ``` 时用整段剩余内容）
                if "```json" in text:
                    start = text.find("```json") + 7
                    end = text.find("```", start)
                    text = text[start:end].strip() if end != -1 else text[start:].strip()
                elif "```" in text:
                    start = text.find("```") + 3
                    end = text.find("```", start)
                    text = text[start:end].strip() if end != -1 else text[start:].strip()
                # 2. 直接解析
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
                # 3. 括号匹配找最外层 {...}，并支持截断修复
                start_idx = text.find("{")
                if start_idx == -1:
                    return {"entities": [], "relations": []}
                depth = 0
                in_string = False
                escape = False
                quote_char = None
                open_bracket = 0  # 未闭合的 [
                n = len(text)
                for i in range(start_idx, n):
                    c = text[i]
                    if escape:
                        escape = False
                        continue
                    if c == "\\" and in_string:
                        escape = True
                        continue
                    if not in_string:
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                            if depth == 0:
                                try:
                                    return json.loads(text[start_idx : i + 1])
                                except json.JSONDecodeError:
                                    pass
                        elif c == "[":
                            open_bracket += 1
                        elif c == "]":
                            open_bracket = max(0, open_bracket - 1)
                        elif c in ('"', "'"):
                            in_string = True
                            quote_char = c
                    elif c == quote_char:
                        in_string = False
                    # 字符串内出现未转义换行（非法 JSON），视为截断或 LLM 换行，退出字符串以便继续匹配
                    elif c == "\n" and in_string:
                        in_string = False
                # 4. 未在循环内返回：可能被截断，尝试补全后解析
                raw = text[start_idx:]
                suffix = (quote_char if in_string else "") + "]" * open_bracket + "}" * depth
                try:
                    return json.loads(raw + suffix)
                except json.JSONDecodeError:
                    pass
                # 5. 再试：只补 } 闭合对象（常见截断在 description 末尾）
                try:
                    return json.loads(raw + (quote_char if in_string else "") + "}" * depth)
                except json.JSONDecodeError:
                    pass
                return {"entities": [], "relations": []}

            result = extract_json(response)
            # 确保返回结构包含 entities 和 relations
            if not isinstance(result, dict):
                result = {"entities": [], "relations": []}
            result.setdefault("entities", [])
            result.setdefault("relations", [])
            if not isinstance(result["entities"], list):
                result["entities"] = []
            if not isinstance(result["relations"], list):
                result["relations"] = []
            if not result["entities"] and not result["relations"] and response.strip():
                logger.warning("LLM 返回解析后实体与关系均为空，原始响应前 500 字符: %s", response[:500])
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
            predicate = "BELONGS_TO"  # 默认关系

        # 关系类型仅允许字母数字下划线（Neo4j 标签/类型规范）
        clean_predicate = re.sub(r'[^a-zA-Z0-9_]', '_', predicate) or "BELONGS_TO"

        # 避免 MATCH (a),(b) 笛卡尔积：先匹配 a，再匹配 b
        query = f"""
        MATCH (a {{name: $subject}})
        WITH a
        MATCH (b {{name: $object}})
        WHERE a <> b
        MERGE (a)-[r:{clean_predicate}]->(b)
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
        轻度认知障碍是介于正常衰老与痴呆之间的阶段。
        患者可能出现记忆减退、执行功能下降等表现。
        日常照护需注意规律作息、防跌倒与按时服药。
        """

        # 处理文本
        result = builder.process_text(test_text)
        print(f"\n处理结果: {result}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
