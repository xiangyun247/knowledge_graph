"""
数据导入脚本
从文本文件或数据源导入知识到图数据库
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
import logging
import json
import time
from typing import List, Dict, Any
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient
from kg.builder import KnowledgeGraphBuilder

# 配置日志
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)


class DataImporter:
    """数据导入器"""

    def __init__(
            self,
            neo4j_client: Neo4jClient,
            llm_client: LLMClient,
            embedding_client: EmbeddingClient
    ):
        """
        初始化数据导入器

        Args:
            neo4j_client: Neo4j 客户端
            llm_client: LLM 客户端
            embedding_client: Embedding 客户端
        """
        self.neo4j = neo4j_client
        self.llm = llm_client
        self.embedding = embedding_client

        # 创建知识图谱构建器
        self.kg_builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )

        logger.info("数据导入器初始化完成")

    def import_from_text_file(self, file_path: str) -> Dict[str, Any]:
        """
        从文本文件导入知识

        Args:
            file_path: 文件路径

        Returns:
            导入统计信息
        """
        logger.info(f"开始从文件导入: {file_path}")

        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"文件读取成功，共 {len(content)} 字符")

            # 分段处理（每 1000 字符一段）
            chunk_size = 1000
            chunks = [
                content[i:i + chunk_size]
                for i in range(0, len(content), chunk_size)
            ]

            logger.info(f"文本分为 {len(chunks)} 段")

            # 处理每一段
            total_stats = {
                "total_chunks": len(chunks),
                "processed_chunks": 0,
                "total_entities": 0,
                "total_relations": 0,
                "errors": 0
            }

            for i, chunk in enumerate(chunks):
                logger.info(f"处理第 {i + 1}/{len(chunks)} 段...")

                try:
                    result = self.kg_builder.process_text(chunk)

                    total_stats["processed_chunks"] += 1
                    total_stats["total_entities"] += result.get("entity_count", 0)
                    total_stats["total_relations"] += result.get("relation_count", 0)

                    logger.info(f"✓ 第 {i + 1} 段处理完成: "
                                f"实体={result.get('entity_count', 0)}, "
                                f"关系={result.get('relation_count', 0)}")

                    # 避免请求过快
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"处理第 {i + 1} 段失败: {e}")
                    total_stats["errors"] += 1

            logger.info(f"文件导入完成: {total_stats}")
            return total_stats

        except Exception as e:
            logger.error(f"文件导入失败: {e}")
            raise

    def import_from_json_file(self, file_path: str) -> Dict[str, Any]:
        """
        从 JSON 文件导入知识

        JSON 格式:
        {
            "entities": [
                {"name": "实体名", "type": "类型", "description": "描述"}
            ],
            "relations": [
                {"subject": "主体", "predicate": "关系", "object": "客体"}
            ]
        }

        Args:
            file_path: JSON 文件路径

        Returns:
            导入统计信息
        """
        logger.info(f"开始从 JSON 文件导入: {file_path}")

        try:
            # 读取 JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            stats = {
                "entities_imported": 0,
                "relations_imported": 0,
                "errors": 0
            }

            # 导入实体
            entities = data.get("entities", [])
            logger.info(f"开始导入 {len(entities)} 个实体...")

            for entity in entities:
                try:
                    self.neo4j.create_node(
                        label=entity.get("type", "Entity"),
                        properties={
                            "name": entity.get("name"),
                            "description": entity.get("description", "")
                        }
                    )
                    stats["entities_imported"] += 1
                except Exception as e:
                    logger.error(f"实体导入失败: {entity.get('name')}, {e}")
                    stats["errors"] += 1

            # 导入关系
            relations = data.get("relations", [])
            logger.info(f"开始导入 {len(relations)} 个关系...")

            for relation in relations:
                try:
                    query = f"""
                    MATCH (a {{name: $subject}}), (b {{name: $object}})
                    MERGE (a)-[r:{relation.get('predicate', 'RELATED_TO')}]->(b)
                    RETURN r
                    """

                    self.neo4j.execute_write(
                        query,
                        {
                            "subject": relation.get("subject"),
                            "object": relation.get("object")
                        }
                    )
                    stats["relations_imported"] += 1
                except Exception as e:
                    logger.error(f"关系导入失败: {relation}, {e}")
                    stats["errors"] += 1

            logger.info(f"JSON 导入完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"JSON 导入失败: {e}")
            raise

    def import_sample_data(self) -> Dict[str, Any]:
        """
        导入示例数据（用于测试）

        Returns:
            导入统计信息
        """
        logger.info("开始导入示例数据...")

        sample_text = """
重症急性胰腺炎（SAP）是急性胰腺炎的严重类型，具有较高的死亡率。
主要症状包括剧烈腹痛、恶心呕吐、发热等。
常见病因包括胆石症和过量饮酒。
诊断方法包括血清淀粉酶检测、CT 扫描等。
治疗措施包括禁食、胃肠减压、抗生素治疗和液体复苏。
可能的并发症包括感染性胰腺坏死、多器官功能衰竭等。
        """

        try:
            result = self.kg_builder.process_text(sample_text.strip())
            logger.info(f"示例数据导入完成: {result}")
            return result
        except Exception as e:
            logger.error(f"示例数据导入失败: {e}")
            raise

    def import_from_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        从目录批量导入文件

        Args:
            directory_path: 目录路径

        Returns:
            总体统计信息
        """
        logger.info(f"开始从目录批量导入: {directory_path}")

        directory = Path(directory_path)

        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")

        # 查找所有文本文件
        text_files = list(directory.glob("*.txt"))
        json_files = list(directory.glob("*.json"))

        logger.info(f"找到 {len(text_files)} 个 .txt 文件")
        logger.info(f"找到 {len(json_files)} 个 .json 文件")

        total_stats = {
            "total_files": len(text_files) + len(json_files),
            "processed_files": 0,
            "total_entities": 0,
            "total_relations": 0,
            "errors": 0
        }

        # 处理文本文件
        for txt_file in text_files:
            logger.info(f"处理文件: {txt_file.name}")
            try:
                result = self.import_from_text_file(str(txt_file))
                total_stats["processed_files"] += 1
                total_stats["total_entities"] += result.get("total_entities", 0)
                total_stats["total_relations"] += result.get("total_relations", 0)
            except Exception as e:
                logger.error(f"文件处理失败: {txt_file.name}, {e}")
                total_stats["errors"] += 1

        # 处理 JSON 文件
        for json_file in json_files:
            logger.info(f"处理文件: {json_file.name}")
            try:
                result = self.import_from_json_file(str(json_file))
                total_stats["processed_files"] += 1
                total_stats["total_entities"] += result.get("entities_imported", 0)
                total_stats["total_relations"] += result.get("relations_imported", 0)
            except Exception as e:
                logger.error(f"文件处理失败: {json_file.name}, {e}")
                total_stats["errors"] += 1

        logger.info(f"目录导入完成: {total_stats}")
        return total_stats


def main():
    """主函数"""
    print("=" * 60)
    print("胰腺炎知识图谱数据导入工具")
    print("=" * 60)

    # 创建客户端
    logger.info("正在连接服务...")
    neo4j_client = Neo4jClient()
    llm_client = LLMClient()
    embedding_client = EmbeddingClient()

    try:
        # 验证连接
        if not neo4j_client.verify_connection():
            logger.error("❌ Neo4j 连接失败")
            return

        if not llm_client.verify_connection():
            logger.error("❌ LLM 连接失败")
            return

        logger.info("✓ 所有服务连接成功")

        # 创建导入器
        importer = DataImporter(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
            embedding_client=embedding_client
        )

        # 显示菜单
        print("\n请选择导入方式:")
        print("1. 导入示例数据（测试用）")
        print("2. 从文本文件导入")
        print("3. 从 JSON 文件导入")
        print("4. 从目录批量导入")
        print("0. 退出")

        choice = input("\n请输入选项 (0-4): ").strip()

        if choice == "1":
            # 导入示例数据
            result = importer.import_sample_data()
            print(f"\n✅ 导入完成!")
            print(f"   实体数: {result.get('entity_count', 0)}")
            print(f"   关系数: {result.get('relation_count', 0)}")

        elif choice == "2":
            # 从文本文件导入
            file_path = input("请输入文本文件路径: ").strip()
            result = importer.import_from_text_file(file_path)
            print(f"\n✅ 导入完成!")
            print(f"   处理段落: {result.get('processed_chunks', 0)}/{result.get('total_chunks', 0)}")
            print(f"   总实体数: {result.get('total_entities', 0)}")
            print(f"   总关系数: {result.get('total_relations', 0)}")
            print(f"   错误数: {result.get('errors', 0)}")

        elif choice == "3":
            # 从 JSON 文件导入
            file_path = input("请输入 JSON 文件路径: ").strip()
            result = importer.import_from_json_file(file_path)
            print(f"\n✅ 导入完成!")
            print(f"   导入实体: {result.get('entities_imported', 0)}")
            print(f"   导入关系: {result.get('relations_imported', 0)}")
            print(f"   错误数: {result.get('errors', 0)}")

        elif choice == "4":
            # 从目录批量导入
            dir_path = input("请输入目录路径: ").strip()
            result = importer.import_from_directory(dir_path)
            print(f"\n✅ 导入完成!")
            print(f"   总文件数: {result.get('total_files', 0)}")
            print(f"   处理文件: {result.get('processed_files', 0)}")
            print(f"   总实体数: {result.get('total_entities', 0)}")
            print(f"   总关系数: {result.get('total_relations', 0)}")
            print(f"   错误数: {result.get('errors', 0)}")

        elif choice == "0":
            print("\n再见！")

        else:
            print("\n❌ 无效选项")

    except KeyboardInterrupt:
        print("\n\n⏹️  导入已取消")
    except Exception as e:
        logger.error(f"导入失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭连接
        neo4j_client.close()
        llm_client.close()
        logger.info("连接已关闭")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
