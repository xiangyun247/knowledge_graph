"""
医疗数据导入脚本
将 JSON 格式的医疗数据导入到 Neo4j 知识图谱
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from neo4j import GraphDatabase
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MedicalDataImporter:
    """医疗数据导入器"""

    def __init__(self):
        """初始化导入器"""
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        logger.info("✓ 已连接到 Neo4j 数据库")

    def close(self):
        """关闭数据库连接"""
        self.driver.close()
        logger.info("✓ 已关闭数据库连接")

    def clear_database(self):
        """清空数据库（谨慎使用！）"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("✓ 数据库已清空")

    def create_indexes(self):
        """创建索引以提升查询性能"""
        indexes = [
            "CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name)",
            "CREATE INDEX symptom_name IF NOT EXISTS FOR (s:Symptom) ON (s.name)",
            "CREATE INDEX drug_name IF NOT EXISTS FOR (dr:Drug) ON (dr.name)",
            "CREATE INDEX department_name IF NOT EXISTS FOR (dep:Department) ON (dep.name)",
        ]

        with self.driver.session() as session:
            for index_query in indexes:
                session.run(index_query)

        logger.info("✓ 索引创建完成")

    def import_diseases(self, diseases: List[Dict[str, Any]]):
        """导入疾病数据"""
        query = """
        UNWIND $diseases AS disease
        MERGE (d:Disease {name: disease.name})
        SET d.category = disease.category,
            d.description = disease.description,
            d.department = disease.department
        """

        with self.driver.session() as session:
            session.run(query, diseases=diseases)

        logger.info(f"✓ 已导入 {len(diseases)} 个疾病")

    def import_symptoms(self, symptoms: List[Dict[str, Any]]):
        """导入症状数据"""
        query = """
        UNWIND $symptoms AS symptom
        MERGE (s:Symptom {name: symptom.name})
        SET s.severity = symptom.severity,
            s.description = symptom.description
        """

        with self.driver.session() as session:
            session.run(query, symptoms=symptoms)

        logger.info(f"✓ 已导入 {len(symptoms)} 个症状")

    def import_drugs(self, drugs: List[Dict[str, Any]]):
        """导入药物数据"""
        query = """
        UNWIND $drugs AS drug
        MERGE (dr:Drug {name: drug.name})
        SET dr.type = drug.type,
            dr.usage = drug.usage,
            dr.dosage = drug.dosage
        """

        with self.driver.session() as session:
            session.run(query, drugs=drugs)

        logger.info(f"✓ 已导入 {len(drugs)} 个药物")

    def import_departments(self, departments: List[Dict[str, Any]]):
        """导入科室数据"""
        query = """
        UNWIND $departments AS dept
        MERGE (d:Department {name: dept.name})
        SET d.description = dept.description
        """

        with self.driver.session() as session:
            session.run(query, departments=departments)

        logger.info(f"✓ 已导入 {len(departments)} 个科室")

    def create_disease_symptom_relations(self, diseases: List[Dict[str, Any]]):
        """创建疾病-症状关系"""
        query = """
        UNWIND $relations AS rel
        MATCH (d:Disease {name: rel.disease})
        MATCH (s:Symptom {name: rel.symptom})
        MERGE (d)-[:HAS_SYMPTOM]->(s)
        """

        relations = []
        for disease in diseases:
            for symptom in disease.get('common_symptoms', []):
                relations.append({
                    'disease': disease['name'],
                    'symptom': symptom
                })

        with self.driver.session() as session:
            session.run(query, relations=relations)

        logger.info(f"✓ 已创建 {len(relations)} 个疾病-症状关系")

    def create_drug_disease_relations(self, drugs: List[Dict[str, Any]]):
        """创建药物-疾病关系"""
        query = """
        UNWIND $relations AS rel
        MATCH (dr:Drug {name: rel.drug})
        MATCH (d:Disease {name: rel.disease})
        MERGE (dr)-[:TREATS]->(d)
        """

        relations = []
        for drug in drugs:
            for disease in drug.get('treats', []):
                relations.append({
                    'drug': drug['name'],
                    'disease': disease
                })

        with self.driver.session() as session:
            session.run(query, relations=relations)

        logger.info(f"✓ 已创建 {len(relations)} 个药物-疾病关系")

    def create_disease_department_relations(self, diseases: List[Dict[str, Any]]):
        """创建疾病-科室关系"""
        query = """
        UNWIND $relations AS rel
        MATCH (d:Disease {name: rel.disease})
        MATCH (dep:Department {name: rel.department})
        MERGE (d)-[:BELONGS_TO]->(dep)
        """

        relations = []
        for disease in diseases:
            if 'department' in disease:
                relations.append({
                    'disease': disease['name'],
                    'department': disease['department']
                })

        with self.driver.session() as session:
            session.run(query, relations=relations)

        logger.info(f"✓ 已创建 {len(relations)} 个疾病-科室关系")

    def import_from_json(self, json_path: str, clear_existing: bool = False):
        """
        从 JSON 文件导入数据

        Args:
            json_path: JSON 文件路径
            clear_existing: 是否清空现有数据
        """
        # 读取 JSON 文件
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"✓ 已读取数据文件: {json_path}")

        # 清空数据库（可选）
        if clear_existing:
            logger.warning("⚠️  正在清空数据库...")
            self.clear_database()

        # 创建索引
        self.create_indexes()

        # 导入实体
        logger.info("\n📊 开始导入实体数据...")
        self.import_diseases(data.get('diseases', []))
        self.import_symptoms(data.get('symptoms', []))
        self.import_drugs(data.get('drugs', []))
        self.import_departments(data.get('departments', []))

        # 创建关系
        logger.info("\n🔗 开始创建关系...")
        self.create_disease_symptom_relations(data.get('diseases', []))
        self.create_drug_disease_relations(data.get('drugs', []))
        self.create_disease_department_relations(data.get('diseases', []))

        logger.info("\n✅ 数据导入完成！")

    def get_statistics(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        queries = {
            'diseases': "MATCH (d:Disease) RETURN count(d) as count",
            'symptoms': "MATCH (s:Symptom) RETURN count(s) as count",
            'drugs': "MATCH (dr:Drug) RETURN count(dr) as count",
            'departments': "MATCH (dep:Department) RETURN count(dep) as count",
            'has_symptom': "MATCH ()-[r:HAS_SYMPTOM]->() RETURN count(r) as count",
            'treats': "MATCH ()-[r:TREATS]->() RETURN count(r) as count",
            'belongs_to': "MATCH ()-[r:BELONGS_TO]->() RETURN count(r) as count",
        }

        stats = {}
        with self.driver.session() as session:
            for name, query in queries.items():
                result = session.run(query)
                stats[name] = result.single()['count']

        return stats


def main():
    """主函数"""
    # 数据文件路径
    data_file = Path(r"C:\Users\23035\PycharmProjects\knowledge_gragh\data\raw\data.json")

    if not data_file.exists():
        logger.error(f"❌ 数据文件不存在: {data_file}")
        logger.info("请先创建数据文件！")
        return

    # 创建导入器
    importer = MedicalDataImporter()

    try:
        # 导入数据（clear_existing=True 会清空现有数据）
        logger.info("🚀 开始导入医疗数据...\n")
        importer.import_from_json(str(data_file), clear_existing=True)

        # 显示统计信息
        logger.info("\n📈 知识图谱统计：")
        stats = importer.get_statistics()
        logger.info(f"  疾病数量: {stats['diseases']}")
        logger.info(f"  症状数量: {stats['symptoms']}")
        logger.info(f"  药物数量: {stats['drugs']}")
        logger.info(f"  科室数量: {stats['departments']}")
        logger.info(f"  疾病-症状关系: {stats['has_symptom']}")
        logger.info(f"  药物-疾病关系: {stats['treats']}")
        logger.info(f"  疾病-科室关系: {stats['belongs_to']}")

    finally:
        importer.close()


if __name__ == "__main__":
    main()
