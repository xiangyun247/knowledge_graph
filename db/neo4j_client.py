"""
Neo4j 数据库客户端
提供连接管理和基础查询功能
"""

import config
from neo4j import GraphDatabase
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 数据库客户端"""

    def __init__(
            self,
            uri: Optional[str] = None,
            user: Optional[str] = None,
            password: Optional[str] = None,
            database: Optional[str] = None
    ):
        """初始化 Neo4j 客户端"""
        self.uri = uri or config.NEO4J_URI
        self.user = user or config.NEO4J_USER
        self.password = password or config.NEO4J_PASSWORD
        self.database = database or config.NEO4J_DATABASE

        if not self.password:
            raise ValueError("Neo4j 密码未配置！请在 .env 文件中设置 NEO4J_PASSWORD")

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            logger.info(f"Neo4j 连接已建立: {self.uri}")
        except Exception as e:
            logger.error(f"Neo4j 连接失败: {e}")
            raise

    def verify_connection(self) -> bool:
        """验证数据库连接是否正常"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                record = result.single()
                if record and record["num"] == 1:
                    logger.info("✓ Neo4j 连接验证成功")
                    return True
                return False
        except Exception as e:
            logger.error(f"连接验证失败: {e}")
            return False

    def execute_query(
            self,
            query: str,
            parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """执行 Cypher 查询"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            logger.error(f"查询语句: {query}")
            logger.error(f"参数: {parameters}")
            raise

    def execute_write(
            self,
            query: str,
            parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行写入操作"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                summary = result.consume()

                return {
                    "nodes_created": summary.counters.nodes_created,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_created": summary.counters.relationships_created,
                    "relationships_deleted": summary.counters.relationships_deleted,
                    "properties_set": summary.counters.properties_set,
                }
        except Exception as e:
            logger.error(f"写入操作失败: {e}")
            logger.error(f"查询语句: {query}")
            logger.error(f"参数: {parameters}")
            raise

    def create_node(
            self,
            label: str,
            properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建节点"""
        query = f"""
        CREATE (n:{label})
        SET n = $properties
        RETURN n
        """
        result = self.execute_query(query, {"properties": properties})
        return result[0]["n"] if result else {}

    def create_relationship(
            self,
            start_node_id: str,
            end_node_id: str,
            rel_type: str,
            properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建关系"""
        query = f"""
        MATCH (a), (b)
        WHERE id(a) = $start_id AND id(b) = $end_id
        CREATE (a)-[r:{rel_type}]->(b)
        SET r = $properties
        RETURN r
        """
        params = {
            "start_id": start_node_id,
            "end_id": end_node_id,
            "properties": properties or {}
        }
        result = self.execute_query(query, params)
        return result[0]["r"] if result else {}

    def find_nodes(
            self,
            label: str,
            properties: Optional[Dict[str, Any]] = None,
            limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查找节点"""
        if properties:
            where_clause = " AND ".join([f"n.{k} = ${k}" for k in properties.keys()])
            query = f"""
            MATCH (n:{label})
            WHERE {where_clause}
            RETURN n
            LIMIT $limit
            """
            params = {**properties, "limit": limit}
        else:
            query = f"""
            MATCH (n:{label})
            RETURN n
            LIMIT $limit
            """
            params = {"limit": limit}

        result = self.execute_query(query, params)
        return [record["n"] for record in result]

    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取节点"""
        query = """
        MATCH (n)
        WHERE id(n) = $node_id
        RETURN n
        """
        result = self.execute_query(query, {"node_id": node_id})
        return result[0]["n"] if result else None

    def delete_all(self):
        """删除所有节点和关系（危险操作，仅用于测试）"""
        query = """
        MATCH (n)
        DETACH DELETE n
        """
        self.execute_write(query)
        logger.warning("⚠️  已删除所有数据")

    def get_statistics(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        queries = {
            "nodes": "MATCH (n) RETURN count(n) AS count",
            "relationships": "MATCH ()-[r]->() RETURN count(r) AS count",
            "labels": "CALL db.labels() YIELD label RETURN count(label) AS count",
            "relationship_types": "CALL db.relationshipTypes() YIELD relationshipType RETURN count(relationshipType) AS count"
        }

        stats = {}
        for key, query in queries.items():
            result = self.execute_query(query)
            stats[key] = result[0]["count"] if result else 0

        return stats

    # ✅ 新增：搜索实体方法（注意缩进在类内部）
    def search_entities(
            self,
            keyword: str,
            node_type: Optional[str] = None,
            limit: int = 10
    ) -> List[Dict]:
        """
        搜索实体

        Args:
            keyword: 搜索关键词
            node_type: 节点类型过滤（可选）
            limit: 返回结果数量限制

        Returns:
            匹配的实体列表
        """
        try:
            # 构建查询
            if node_type:
                query = """
                MATCH (n)
                WHERE n.name CONTAINS $keyword 
                  AND $node_type IN labels(n)
                RETURN n, labels(n) as labels
                LIMIT $limit
                """
                params = {
                    "keyword": keyword,
                    "node_type": node_type,
                    "limit": limit
                }
            else:
                query = """
                MATCH (n)
                WHERE n.name CONTAINS $keyword
                RETURN n, labels(n) as labels
                LIMIT $limit
                """
                params = {
                    "keyword": keyword,
                    "limit": limit
                }

            results = self.execute_query(query, params)

            # 格式化结果
            entities = []
            for record in results:
                node = record['n']
                labels = record['labels']

                entity = {
                    'id': node.element_id if hasattr(node, 'element_id') else str(id(node)),
                    'type': labels[0] if labels else 'Unknown',
                    'name': node.get('name', ''),
                    'properties': dict(node)
                }
                entities.append(entity)

            logger.info(f"搜索 '{keyword}' 找到 {len(entities)} 个结果")
            return entities

        except Exception as e:
            logger.error(f"搜索实体失败: {e}")
            return []

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("Neo4j 连接已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

    def __del__(self):
        """析构函数"""
        self.close()


# 便捷函数
def create_client(**kwargs) -> Neo4jClient:
    """创建 Neo4j 客户端的便捷函数"""
    return Neo4jClient(**kwargs)


# 示例用法
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Neo4j 客户端测试")
    print("=" * 60)

    with Neo4jClient() as client:
        if client.verify_connection():
            print("✓ 连接验证成功")

        stats = client.get_statistics()
        print(f"\n数据库统计:")
        print(f"  节点数: {stats['nodes']}")
        print(f"  关系数: {stats['relationships']}")
        print(f"  标签数: {stats['labels']}")
        print(f"  关系类型数: {stats['relationship_types']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
