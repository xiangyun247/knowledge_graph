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
                    logger.info("[OK] Neo4j 连接验证成功")
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
                records = []
                for record in result:
                    data = record.data()
                    # 确保 labels 是列表格式（如果是其他格式，转换为列表）
                    if 'labels' in data:
                        labels = data['labels']
                        if not isinstance(labels, list):
                            if labels is None:
                                data['labels'] = []
                            else:
                                data['labels'] = [labels] if labels else []
                    records.append(data)
                return records
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

    def get_all_nodes_and_relationships(
            self,
            limit: Optional[int] = None,
            offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取所有节点和关系（用于知识图谱可视化）

        Args:
            limit: 节点数量限制（可选）
            offset: 偏移量（可选）

        Returns:
            包含 nodes 和 relationships 的字典
        """
        try:
            # 构建节点查询
            node_query = """
            MATCH (n)
            RETURN n, labels(n) as labels, id(n) as node_id
            """
            
            if limit is not None:
                node_query += f" SKIP {offset or 0} LIMIT {limit}"
            
            node_results = self.execute_query(node_query)
            
            # 格式化节点
            nodes = []
            node_id_map = {}  # 映射 Neo4j 内部 ID 到节点索引
            
            for idx, record in enumerate(node_results):
                node = record['n']
                labels = record.get('labels', [])
                neo4j_id = record.get('node_id')
                
                # 确保 labels 是列表格式
                if not isinstance(labels, list):
                    if labels is None:
                        labels = []
                    else:
                        labels = [labels] if labels else []
                
                # 获取节点属性
                node_props = dict(node) if hasattr(node, 'keys') else {}
                node_name = node_props.get('name', node_props.get('title', f'Node_{neo4j_id}'))
                
                # 获取节点类型（优先使用 labels，如果没有则尝试从 properties 中获取）
                if labels and len(labels) > 0:
                    node_type = str(labels[0])  # 确保是字符串
                elif 'type' in node_props:
                    node_type = str(node_props.get('type'))
                elif 'category' in node_props:
                    node_type = str(node_props.get('category'))
                else:
                    # 如果都没有，记录警告并尝试从节点属性推断
                    logger.warning(f"节点 {node_name} (ID: {neo4j_id}) 没有 labels，labels={labels}, 尝试从属性推断类型")
                    # 尝试从节点属性中推断类型
                    node_type = 'Unknown'
                    # 如果节点有 description 属性，可能是疾病
                    if 'description' in node_props:
                        node_type = 'Disease'  # 默认推断为疾病
                
                # 将节点类型转换为小写，以匹配前端期望的格式
                # 前端期望: 'disease', 'symptom', 'treatment', 'medicine', 'examination', 'location'
                # 后端返回: 'Disease', 'Symptom', 'Treatment', 'Medicine', 'Examination', 'Department'
                node_type_lower = node_type.lower()
                
                # 类型映射：将后端类型映射到前端期望的类型
                type_mapping = {
                    'disease': 'disease',
                    'symptom': 'symptom',
                    'treatment': 'treatment',
                    'medicine': 'medicine',
                    'examination': 'examination',
                    'department': 'location',  # Department 映射到 location
                    'complication': 'disease',  # Complication 映射到 disease
                    'riskfactor': 'disease',  # RiskFactor 映射到 disease
                    'unknown': 'disease'  # Unknown 默认映射到 disease
                }
                
                # 使用映射后的类型，如果没有映射则使用小写类型
                mapped_category = type_mapping.get(node_type_lower, node_type_lower)
                
                # 记录前几个节点的信息用于调试
                if idx < 5:
                    logger.info(f"[DEBUG] 节点 {idx}: name={node_name}, labels={labels}, node_type={node_type}, mapped_category={mapped_category}")
                
                # 生成前端需要的节点格式
                node_data = {
                    'id': str(neo4j_id),  # 使用 Neo4j 内部 ID 作为唯一标识
                    'name': node_name,
                    'category': mapped_category,  # 使用映射后的类型
                    'label': node_name,
                    'type': node_type,  # 保留原始类型
                    'properties': node_props
                }
                
                nodes.append(node_data)
                node_id_map[neo4j_id] = idx
            
            # 获取关系（只获取与返回节点相关的关系）
            if nodes:
                node_ids_str = ','.join([str(record['node_id']) for record in node_results])
                rel_query = f"""
                MATCH (a)-[r]->(b)
                WHERE id(a) IN [{node_ids_str}] AND id(b) IN [{node_ids_str}]
                RETURN id(a) as start_id, id(b) as end_id, type(r) as rel_type, r, properties(r) as rel_props
                """
            else:
                rel_query = """
                MATCH (a)-[r]->(b)
                RETURN id(a) as start_id, id(b) as end_id, type(r) as rel_type, r, properties(r) as rel_props
                LIMIT 0
                """
            
            rel_results = self.execute_query(rel_query)
            
            # 格式化关系
            relationships = []
            for record in rel_results:
                start_id = record['start_id']
                end_id = record['end_id']
                rel_type = record['rel_type']
                rel_props = record['rel_props']
                
                # 生成前端需要的关系格式
                rel_data = {
                    'id': f"{start_id}_{end_id}_{rel_type}",
                    'source': str(start_id),
                    'target': str(end_id),
                    'label': rel_type,
                    'type': rel_type,
                    'relation': rel_type,
                    'properties': rel_props
                }
                
                relationships.append(rel_data)
            
            logger.info(f"从 Neo4j 获取了 {len(nodes)} 个节点和 {len(relationships)} 个关系")
            
            return {
                'nodes': nodes,
                'relationships': relationships
            }
            
        except Exception as e:
            logger.error(f"获取所有节点和关系失败: {e}")
            return {'nodes': [], 'relationships': []}

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
