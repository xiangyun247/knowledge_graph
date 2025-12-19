import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

import config
from db.neo4j_client import Neo4jClient
from llm.client import create_client
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DiseaseDataImporter:
    """疾病数据导入器"""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self.stats = {
            "diseases": 0,
            "symptoms": 0,
            "departments": 0,
            "drugs": 0,
            "checks": 0,
            "complications": 0,
            "relations": 0
        }

    def import_from_json(self, json_file: Path):
        """从JSON文件导入数据"""
        logger.info(f"开始从 {json_file} 导入数据...")

        # 读取JSON文件
        with open(json_file, 'r', encoding='utf-8') as f:
            # 逐行读取（因为你的JSON是每行一个对象）
            diseases = []
            for line in f:
                line = line.strip()
                if line:
                    try:
                        disease = json.loads(line)
                        diseases.append(disease)
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析JSON失败: {e}")
                        continue

        logger.info(f"成功读取 {len(diseases)} 条疾病数据")

        # 导入数据
        for disease in diseases:
            self._import_single_disease(disease)

        # 打印统计信息
        self._print_stats()

    def _import_single_disease(self, disease: Dict[str, Any]):
        """导入单个疾病数据"""
        try:
            disease_name = disease.get("name", "")
            if not disease_name:
                logger.warning("疾病名称为空，跳过")
                return

            # 1. 创建疾病节点
            self._create_disease_node(disease)

            # 2. 创建症状节点和关系
            self._create_symptoms(disease_name, disease.get("symptom", []))

            # 3. 创建科室节点和关系
            self._create_departments(disease_name, disease.get("cure_department", []))

            # 4. 创建药物节点和关系
            self._create_drugs(disease_name, disease.get("recommand_drug", []))

            # 5. 创建检查项目节点和关系
            self._create_checks(disease_name, disease.get("check", []))

            # 6. 创建并发症节点和关系
            self._create_complications(disease_name, disease.get("acompany", []))

            logger.info(f"✓ 成功导入疾病: {disease_name}")

        except Exception as e:
            logger.error(f"导入疾病失败: {disease.get('name', 'Unknown')} - {e}")

    def _create_disease_node(self, disease: Dict[str, Any]):
        """创建疾病节点"""
        cypher = """
        MERGE (d:Disease {name: $name})
        SET d.description = $description,
            d.category = $category,
            d.cause = $cause,
            d.prevent = $prevent,
            d.get_way = $get_way,
            d.get_prob = $get_prob,
            d.cure_way = $cure_way,
            d.cure_lasttime = $cure_lasttime,
            d.cured_prob = $cured_prob,
            d.cost_money = $cost_money,
            d.yibao_status = $yibao_status
        RETURN d
        """

        params = {
            "name": disease.get("name", ""),
            "description": disease.get("desc", ""),
            "category": ", ".join(disease.get("category", [])),
            "cause": disease.get("cause", ""),
            "prevent": disease.get("prevent", ""),
            "get_way": disease.get("get_way", ""),
            "get_prob": disease.get("get_prob", ""),
            "cure_way": ", ".join(disease.get("cure_way", [])),
            "cure_lasttime": disease.get("cure_lasttime", ""),
            "cured_prob": disease.get("cured_prob", ""),
            "cost_money": disease.get("cost_money", ""),
            "yibao_status": disease.get("yibao_status", "")
        }

        self.neo4j_client.execute_query(cypher, params)
        self.stats["diseases"] += 1

    def _create_symptoms(self, disease_name: str, symptoms: List[str]):
        """创建症状节点和关系"""
        for symptom in symptoms:
            if not symptom:
                continue

            # 创建症状节点
            cypher_node = """
            MERGE (s:Symptom {name: $symptom})
            RETURN s
            """
            self.neo4j_client.execute_query(cypher_node, {"symptom": symptom})
            self.stats["symptoms"] += 1

            # 创建关系
            cypher_rel = """
            MATCH (d:Disease {name: $disease})
            MATCH (s:Symptom {name: $symptom})
            MERGE (d)-[:HAS_SYMPTOM]->(s)
            """
            self.neo4j_client.execute_query(cypher_rel, {
                "disease": disease_name,
                "symptom": symptom
            })
            self.stats["relations"] += 1

    def _create_departments(self, disease_name: str, departments: List[str]):
        """创建科室节点和关系"""
        for dept in departments:
            if not dept:
                continue

            # 创建科室节点
            cypher_node = """
            MERGE (d:Department {name: $dept})
            RETURN d
            """
            self.neo4j_client.execute_query(cypher_node, {"dept": dept})
            self.stats["departments"] += 1

            # 创建关系
            cypher_rel = """
            MATCH (disease:Disease {name: $disease})
            MATCH (dept:Department {name: $dept})
            MERGE (disease)-[:BELONGS_TO]->(dept)
            """
            self.neo4j_client.execute_query(cypher_rel, {
                "disease": disease_name,
                "dept": dept
            })
            self.stats["relations"] += 1

    def _create_drugs(self, disease_name: str, drugs: List[str]):
        """创建药物节点和关系"""
        for drug in drugs:
            if not drug:
                continue

            # 创建药物节点
            cypher_node = """
            MERGE (m:Medicine {name: $drug})
            RETURN m
            """
            self.neo4j_client.execute_query(cypher_node, {"drug": drug})
            self.stats["drugs"] += 1

            # 创建关系
            cypher_rel = """
            MATCH (d:Disease {name: $disease})
            MATCH (m:Medicine {name: $drug})
            MERGE (d)-[:USES_MEDICINE]->(m)
            """
            self.neo4j_client.execute_query(cypher_rel, {
                "disease": disease_name,
                "drug": drug
            })
            self.stats["relations"] += 1

    def _create_checks(self, disease_name: str, checks: List[str]):
        """创建检查项目节点和关系"""
        for check in checks:
            if not check:
                continue

            # 创建检查节点
            cypher_node = """
            MERGE (e:Examination {name: $check})
            RETURN e
            """
            self.neo4j_client.execute_query(cypher_node, {"check": check})
            self.stats["checks"] += 1

            # 创建关系
            cypher_rel = """
            MATCH (d:Disease {name: $disease})
            MATCH (e:Examination {name: $check})
            MERGE (d)-[:REQUIRES_EXAM]->(e)
            """
            self.neo4j_client.execute_query(cypher_rel, {
                "disease": disease_name,
                "check": check
            })
            self.stats["relations"] += 1

    def _create_complications(self, disease_name: str, complications: List[str]):
        """创建并发症节点和关系"""
        for comp in complications:
            if not comp:
                continue

            # 创建并发症节点（作为疾病的一种）
            cypher_node = """
            MERGE (c:Complication {name: $comp})
            RETURN c
            """
            self.neo4j_client.execute_query(cypher_node, {"comp": comp})
            self.stats["complications"] += 1

            # 创建关系
            cypher_rel = """
            MATCH (d:Disease {name: $disease})
            MATCH (c:Complication {name: $comp})
            MERGE (d)-[:LEADS_TO]->(c)
            """
            self.neo4j_client.execute_query(cypher_rel, {
                "disease": disease_name,
                "comp": comp
            })
            self.stats["relations"] += 1

    def _print_stats(self):
        """打印统计信息"""
        logger.info("=" * 50)
        logger.info("数据导入完成！统计信息：")
        logger.info(f"  疾病数量: {self.stats['diseases']}")
        logger.info(f"  症状数量: {self.stats['symptoms']}")
        logger.info(f"  科室数量: {self.stats['departments']}")
        logger.info(f"  药物数量: {self.stats['drugs']}")
        logger.info(f"  检查项目数量: {self.stats['checks']}")
        logger.info(f"  并发症数量: {self.stats['complications']}")
        logger.info(f"  关系数量: {self.stats['relations']}")
        logger.info("=" * 50)


def main():
    """主函数"""
    # 你的JSON文件路径
    json_file = config.RAW_DATA_DIR / "data.json"  # 改成你的文件名

    if not json_file.exists():
        logger.error(f"数据文件不存在: {json_file}")
        logger.info(f"请将JSON文件放到: {config.RAW_DATA_DIR}")
        return

    # 初始化Neo4j客户端
    neo4j_client = Neo4jClient(
        uri=config.NEO4J_URI,
        user=config.NEO4J_USER,
        password=config.NEO4J_PASSWORD
    )

    try:
        # 创建导入器并导入数据
        importer = DiseaseDataImporter(neo4j_client)
        importer.import_from_json(json_file)

    except Exception as e:
        logger.error(f"导入失败: {e}")
    finally:
        neo4j_client.close()


if __name__ == "__main__":
    main()
