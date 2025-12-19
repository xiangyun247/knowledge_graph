"""
数据库初始化脚本
创建索引、约束，并导入初始数据
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
import config  # ✅ 修改这里
from config import print_config_summary
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from kg.builder import KnowledgeGraphBuilder

# 配置日志
logging.basicConfig(
    level=config.LOG_LEVEL,  # ✅ 使用 config.LOG_LEVEL
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_schema(client: Neo4jClient):
    """创建数据库模式（索引和约束）"""
    logger.info("正在创建索引和约束...")

    # 为每个实体类型创建唯一约束
    entity_types = config.ENTITY_TYPES  # ✅ 使用 config.XXX

    for entity_type in entity_types:
        try:
            # 创建唯一约束（自动创建索引）
            query = f"""
            CREATE CONSTRAINT {entity_type.lower()}_name_unique IF NOT EXISTS
            FOR (n:{entity_type})
            REQUIRE n.name IS UNIQUE
            """
            client.execute_write(query)
            logger.info(f"  ✓ 创建约束: {entity_type}.name")
        except Exception as e:
            logger.warning(f"  ⚠️  约束可能已存在: {entity_type}.name - {e}")

    # 创建全文索引
    try:
        query = """
        CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
        FOR (n:Disease|Symptom|Treatment|Medicine|Examination|Department|Complication|RiskFactor)
        ON EACH [n.name, n.description]
        """
        client.execute_write(query)
        logger.info("  ✓ 创建全文索引")
    except Exception as e:
        logger.warning(f"  ⚠️  全文索引可能已存在 - {e}")

    logger.info("✓ 数据库模式创建完成")


def import_initial_data(kg_builder: KnowledgeGraphBuilder):
    """导入初始数据"""
    logger.info("正在导入胰腺炎知识数据...")

    # 初始知识数据
    initial_knowledge = """
    重症急性胰腺炎（SAP）是一种严重的胰腺炎症。

    主要症状包括：
    - 剧烈腹痛
    - 恶心呕吐
    - 发热
    - 腹胀

    常用治疗方法：
    - 禁食禁水
    - 静脉营养支持
    - 抗生素治疗
    - 镇痛治疗

    常用药物包括：
    - 奥美拉唑（抑制胃酸）
    - 头孢类抗生素
    - 生长抑素

    需要的检查：
    - 血淀粉酶检查
    - CT扫描
    - 超声检查

    可能的并发症：
    - 胰腺坏死
    - 感染
    - 多器官功能衰竭

    风险因素：
    - 胆结石
    - 酗酒
    - 高脂血症
    """

    try:
        # 使用知识图谱构建器处理文本
        kg_builder.process_text(initial_knowledge)
        logger.info("✓ 初始数据导入完成")
    except Exception as e:
        logger.error(f"❌ 数据导入失败: {e}")
        raise


def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("数据库初始化脚本")
    logger.info("=" * 60 + "\n")

    # 显示配置摘要
    print_config_summary()

    neo4j_client = None
    llm_client = None

    try:
        # 初始化 Neo4j 客户端
        logger.info("正在连接 Neo4j...")
        neo4j_client = Neo4jClient(
            uri=config.NEO4J_URI,  # ✅ config.XXX
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD,
            database=config.NEO4J_DATABASE
        )

        # 验证 Neo4j 连接
        if not neo4j_client.verify_connection():
            logger.error("❌ Neo4j 连接失败")
            logger.error("连接失败，退出")
            return False

        logger.info("✓ Neo4j 连接成功")

        # 初始化 LLM 客户端
        logger.info("正在连接 LLM 服务...")
        llm_client = LLMClient(
            api_key=config.DEEPSEEK_API_KEY,  # ✅ config.XXX
            base_url=config.DEEPSEEK_BASE_URL,
            model=config.DEEPSEEK_MODEL,
        )

        # 验证 LLM 连接
        if not llm_client.verify_connection():
            logger.error("❌ LLM 连接失败")
            logger.error("连接失败，退出")
            return False

        logger.info("✓ LLM 连接成功")

        # 创建数据库模式
        create_schema(neo4j_client)

        # 初始化知识图谱构建器
        logger.info("正在初始化知识图谱构建器...")
        kg_builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client
        )
        logger.info("✓ 知识图谱构建器初始化完成")

        # 导入初始数据
        import_initial_data(kg_builder)

        # 显示统计信息
        stats = neo4j_client.get_statistics()
        logger.info("\n数据库统计:")
        logger.info(f"  节点数: {stats['nodes']}")
        logger.info(f"  关系数: {stats['relationships']}")
        logger.info(f"  标签数: {stats['labels']}")
        logger.info(f"  关系类型数: {stats['relationship_types']}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 数据库初始化完成！")
        logger.info("=" * 60 + "\n")

        return True

    except Exception as e:
        logger.error(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 关闭连接
        if neo4j_client:
            neo4j_client.close()
            logger.info("✓ 已关闭数据库连接")
        if llm_client:
            llm_client.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
