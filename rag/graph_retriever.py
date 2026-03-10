"""
图检索器
从知识图谱中检索相关信息
支持多跳检索、路径查找、子图提取
"""

import config
from config import ENTITY_TYPE_EN_TO_ZH
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphRetriever:
    """图检索器"""

    def __init__(self, neo4j_client: Neo4jClient):
        """
        初始化图检索器

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.neo4j = neo4j_client
        self.max_depth = config.MAX_GRAPH_DEPTH
        self.entity_types = config.ENTITY_TYPES
        self.relation_types = config.RELATION_TYPES

        logger.info(f"图检索器初始化完成，最大深度: {self.max_depth}")

    def retrieve(
            self,
            query: str,
            entity_names: List[str],
            max_depth: Optional[int] = None,
            limit: int = 50,
            preferred_relation_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        从图中检索相关信息

        Args:
            query: 用户查询
            entity_names: 识别出的实体名称列表
            max_depth: 最大检索深度，默认从 config 读取
            limit: 返回结果数量限制
            preferred_relation_types: 意图相关的关系类型，匹配时提升排序

        Returns:
            检索结果列表，每个结果包含实体、关系和路径信息
        """
        depth = max_depth if max_depth is not None else self.max_depth

        if not entity_names:
            logger.warning("未提供实体名称，返回空结果")
            return []

        logger.info(f"开始图检索: 实体={entity_names}, 深度={depth}, 限制={limit}")

        results = []

        try:
            # 1. 直接检索实体及其属性
            direct_results = self._retrieve_direct_entities(entity_names)
            results.extend(direct_results)

            # 2. 检索多跳邻居
            neighbor_results = self._retrieve_multi_hop_neighbors(
                entity_names,
                depth=depth,
                limit=limit
            )
            results.extend(neighbor_results)

            # 3. 检索实体间的路径
            if len(entity_names) >= 2:
                path_results = self._retrieve_paths_between_entities(
                    entity_names,
                    max_depth=depth
                )
                results.extend(path_results)

            # 4. 去重和排序（支持意图相关关系类型加权）
            results = self._deduplicate_and_rank(
                results, query, preferred_relation_types=preferred_relation_types
            )

            # 5. 限制返回数量
            results = results[:limit]

            logger.info(f"图检索完成，共返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"图检索失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _retrieve_direct_entities(
            self,
            entity_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        直接检索实体及其属性

        Args:
            entity_names: 实体名称列表

        Returns:
            实体信息列表
        """
        if not entity_names:
            return []

        query = """
        MATCH (n)
        WHERE n.name IN $entity_names
        RETURN n, labels(n) as labels, id(n) as node_id
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"entity_names": entity_names}
            )

            results = []
            for record in records:
                node = record["n"]
                results.append({
                    "type": "entity",
                    "node_id": record["node_id"],
                    "labels": record["labels"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "properties": dict(node),
                    "relevance_score": 1.0,  # 直接匹配的实体给最高分
                    "source": "direct_match"
                })

            logger.debug(f"直接检索到 {len(results)} 个实体")
            return results

        except Exception as e:
            logger.error(f"直接实体检索失败: {e}")
            return []

    def _retrieve_multi_hop_neighbors(
            self,
            entity_names: List[str],
            depth: int = 2,
            limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        检索多跳邻居节点

        Args:
            entity_names: 起始实体名称列表
            depth: 检索深度（1-3）
            limit: 返回数量限制

        Returns:
            邻居节点及关系信息列表
        """
        if not entity_names or depth < 1:
            return []

        # 限制深度，避免查询过慢
        depth = min(depth, 3)

        query = f"""
        MATCH path = (start)-[*1..{depth}]-(neighbor)
        WHERE start.name IN $entity_names
        WITH path, neighbor, start, length(path) as hop_count
        ORDER BY hop_count, neighbor.name
        LIMIT $limit
        RETURN 
            neighbor,
            labels(neighbor) as labels,
            id(neighbor) as node_id,
            hop_count,
            [rel in relationships(path) | type(rel)] as rel_types,
            [node in nodes(path) | node.name] as path_names
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"entity_names": entity_names, "limit": limit}
            )

            results = []
            for record in records:
                node = record["neighbor"]
                hop_count = record["hop_count"]

                # 根据跳数计算相关性分数（跳数越少，分数越高）
                relevance_score = 1.0 / (1.0 + 0.3 * hop_count)

                results.append({
                    "type": "neighbor",
                    "node_id": record["node_id"],
                    "labels": record["labels"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "properties": dict(node),
                    "hop_count": hop_count,
                    "path_names": record["path_names"],
                    "relation_types": record["rel_types"],
                    "relevance_score": relevance_score,
                    "source": f"{hop_count}_hop_neighbor"
                })

            logger.debug(f"检索到 {len(results)} 个邻居节点")
            return results

        except Exception as e:
            logger.error(f"多跳邻居检索失败: {e}")
            return []

    def _retrieve_paths_between_entities(
            self,
            entity_names: List[str],
            max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        检索实体之间的最短路径

        Args:
            entity_names: 实体名称列表
            max_depth: 最大路径长度

        Returns:
            路径信息列表
        """
        if len(entity_names) < 2:
            return []

        # 限制路径长度
        max_depth = min(max_depth, 5)

        query = f"""
        MATCH (start), (end)
        WHERE start.name IN $entity_names AND end.name IN $entity_names
            AND start.name <> end.name
        MATCH path = shortestPath((start)-[*1..{max_depth}]-(end))
        WITH path, start, end, length(path) as path_length
        RETURN 
            start.name as start_name,
            end.name as end_name,
            path_length,
            [node in nodes(path) | {{name: node.name, labels: labels(node)}}] as path_nodes,
            [rel in relationships(path) | type(rel)] as rel_types
        LIMIT 10
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"entity_names": entity_names}
            )

            results = []
            for record in records:
                path_length = record["path_length"]

                # 路径越短，相关性越高
                relevance_score = 1.0 / (1.0 + 0.2 * path_length)

                results.append({
                    "type": "path",
                    "start_entity": record["start_name"],
                    "end_entity": record["end_name"],
                    "path_length": path_length,
                    "path_nodes": record["path_nodes"],
                    "relation_types": record["rel_types"],
                    "relevance_score": relevance_score,
                    "source": "entity_path"
                })

            logger.debug(f"检索到 {len(results)} 条实体间路径")
            return results

        except Exception as e:
            logger.error(f"路径检索失败: {e}")
            return []

    def retrieve_by_relation(
            self,
            entity_name: str,
            relation_type: Optional[str] = None,
            direction: str = "both",  # "outgoing", "incoming", "both"
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        根据关系类型检索相关实体

        Args:
            entity_name: 实体名称
            relation_type: 关系类型，None 表示所有类型
            direction: 关系方向
            limit: 返回数量限制

        Returns:
            相关实体列表
        """
        # 构建关系模式
        if direction == "outgoing":
            rel_pattern = "-[r]->"
        elif direction == "incoming":
            rel_pattern = "<-[r]-"
        else:  # both
            rel_pattern = "-[r]-"

        # 构建关系类型过滤
        rel_type_filter = f":{relation_type}" if relation_type else ""

        query = f"""
        MATCH (source {{name: $entity_name}}){rel_pattern[:3]}{rel_type_filter}{rel_pattern[3:]}(target)
        RETURN 
            target,
            labels(target) as labels,
            id(target) as node_id,
            type(r) as relation_type,
            properties(r) as relation_props
        LIMIT $limit
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"entity_name": entity_name, "limit": limit}
            )

            results = []
            for record in records:
                node = record["target"]
                results.append({
                    "type": "related_entity",
                    "node_id": record["node_id"],
                    "labels": record["labels"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "properties": dict(node),
                    "relation_type": record["relation_type"],
                    "relation_properties": record["relation_props"],
                    "relevance_score": 0.8,
                    "source": f"relation_{relation_type or 'any'}"
                })

            logger.debug(f"通过关系检索到 {len(results)} 个实体")
            return results

        except Exception as e:
            logger.error(f"关系检索失败: {e}")
            return []

    def retrieve_subgraph(
            self,
            entity_names: List[str],
            depth: int = 2,
            min_relevance: float = 0.5
    ) -> Dict[str, Any]:
        """
        提取以指定实体为中心的子图

        Args:
            entity_names: 中心实体名称列表
            depth: 子图深度
            min_relevance: 最小相关性阈值

        Returns:
            子图数据，包含节点和边
        """
        if not entity_names:
            return {"nodes": [], "edges": []}

        depth = min(depth, 3)  # 限制深度

        query = f"""
        MATCH path = (center)-[*0..{depth}]-(node)
        WHERE center.name IN $entity_names
        WITH collect(DISTINCT node) as nodes, 
             collect(DISTINCT [n in nodes(path) | id(n)]) as node_id_paths,
             collect(DISTINCT [r in relationships(path) | {{
                 id: id(r),
                 type: type(r),
                 start: id(startNode(r)),
                 end: id(endNode(r)),
                 properties: properties(r)
             }}]) as edge_lists
        RETURN 
            [n in nodes | {{
                id: id(n),
                labels: labels(n),
                properties: properties(n)
            }}] as nodes,
            reduce(acc = [], edge_list in edge_lists | acc + edge_list) as edges
        """

        try:
            records = self.neo4j.execute_query(
                query,
                {"entity_names": entity_names}
            )

            if not records:
                return {"nodes": [], "edges": []}

            record = records[0]

            # 去重边
            unique_edges = {}
            for edge in record["edges"]:
                edge_id = edge.get("id")
                if edge_id not in unique_edges:
                    unique_edges[edge_id] = edge

            result = {
                "nodes": record["nodes"],
                "edges": list(unique_edges.values()),
                "node_count": len(record["nodes"]),
                "edge_count": len(unique_edges)
            }

            logger.debug(f"提取子图: {result['node_count']} 个节点, {result['edge_count']} 条边")
            return result

        except Exception as e:
            logger.error(f"子图提取失败: {e}")
            return {"nodes": [], "edges": []}

    def _deduplicate_and_rank(
            self,
            results: List[Dict[str, Any]],
            query: str,
            preferred_relation_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        去重并排序结果。当 preferred_relation_types 非空时，路径/邻居结果中
        若包含这些关系类型，则提升 relevance_score。
        """
        if not results:
            return []

        preferred = set(preferred_relation_types or [])

        def _boost_score(r: Dict) -> float:
            score = r.get("relevance_score", 0)
            rel_types = r.get("relation_types") or []
            if preferred and any(rt in preferred for rt in rel_types):
                score += 0.2  # 意图相关关系加权
            return min(1.0, score)

        # 去重（基于 node_id 或 path 唯一键）
        unique_results = {}
        for result in results:
            key = result.get("node_id")
            if key is None and result.get("type") == "path":
                key = f"path:{result.get('start_entity','')}->{result.get('end_entity','')}"
            if key is None:
                key = result.get("name") or str(result)

            boosted = {**result, "relevance_score": _boost_score(result)}
            if key in unique_results:
                if boosted.get("relevance_score", 0) > unique_results[key].get("relevance_score", 0):
                    unique_results[key] = boosted
            else:
                unique_results[key] = boosted

        unique_list = list(unique_results.values())
        sorted_results = sorted(
            unique_list,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )

        logger.debug(f"去重前: {len(results)} 个结果, 去重后: {len(sorted_results)} 个结果")
        return sorted_results

    def format_results_for_context(
            self,
            results: List[Dict[str, Any]],
            max_length: int = 2000
    ) -> str:
        """
        将检索结果格式化为上下文文本

        Args:
            results: 检索结果列表
            max_length: 最大文本长度

        Returns:
            格式化的上下文文本
        """
        if not results:
            return ""

        context_parts = []
        current_length = 0

        for i, result in enumerate(results):
            result_type = result.get("type", "unknown")

            if result_type == "entity":
                text = f"实体：{result.get('name', '')} ({', '.join(result.get('labels', []))})\n"
                desc = result.get("description", "")
                if desc:
                    text += f"描述：{desc}\n"

            elif result_type == "neighbor":
                text = f"相关实体：{result.get('name', '')} (距离: {result.get('hop_count', 0)} 跳)\n"
                path = " -> ".join(result.get("path_names", []))
                text += f"路径：{path}\n"

            elif result_type == "path":
                text = f"路径：{result.get('start_entity', '')} -> {result.get('end_entity', '')}\n"
                rels = " -> ".join(result.get("relation_types", []))
                text += f"关系：{rels}\n"

            else:
                text = f"{result}\n"

            text += "\n"

            if current_length + len(text) > max_length:
                break

            context_parts.append(text)
            current_length += len(text)

        context = "".join(context_parts)
        logger.debug(f"格式化上下文: {len(context)} 字符, 包含 {len(context_parts)} 个结果")

        return context

    def get_graph_data(
            self,
            node_label: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        获取图谱数据用于前端可视化

        Args:
            node_label: 节点标签过滤
            limit: 返回结果数量限制
            offset: 偏移量，用于分页

        Returns:
            节点列表和边列表
        """
        try:
            logger.info(f"获取图谱数据，标签: {node_label}, 限制: {limit}, 偏移量: {offset}")

            # 构建节点查询
            if node_label:
                node_query = f"""
                MATCH (n:{node_label})
                RETURN n, labels(n) as labels, id(n) as node_id
                ORDER BY id(n)
                SKIP $offset
                LIMIT $limit
                """
            else:
                node_query = """
                MATCH (n)
                RETURN n, labels(n) as labels, id(n) as node_id
                ORDER BY id(n)
                SKIP $offset
                LIMIT $limit
                """

            # 执行节点查询
            node_records = self.neo4j.execute_query(
                node_query,
                {"limit": limit, "offset": offset}
            )

            # 构建节点列表
            nodes = []
            node_ids = set()

            # 节点类型到颜色映射（按表2 实体分类）
            NODE_COLOR_MAP = {
                "Disease": "#ff6b6b",
                "Symptom": "#4ecdc4",
                "Population": "#a29bfe",
                "Medicine": "#55efc4",
                "Prognosis": "#74b9ff",
                "PhysicalExamination": "#ffeaa7",
                "LaboratoryExamination": "#fdcb6e",
                "ImagingExamination": "#e17055",
                "PathologyExamination": "#d63031",
                "OtherExamination": "#e84393",
                "AbnormalExaminationResult": "#fd79a8",
                "TCMTreatment": "#00b894",
                "Surgery": "#0984e3",
                "DrugTreatment": "#6c5ce7",
                "WesternPhysicalTherapy": "#00cec9",
                "OtherTreatment": "#81ecec",
                "AnatomicalSite": "#dfe6e9",
                "AnatomicalSubstance": "#b2bec3",
                "MedicalEquipment": "#636e72",
                "Hospital": "#2d3436",
                "Department": "#fab1a0",
                "Gene": "#a8e6cf",
                "Microorganism": "#ff8b94",
                "PhysicalChemicalFactor": "#ffaaa5",
                "PsychologicalBehavior": "#ffd3b6",
                "Lifestyle": "#dcedd2",
                "ImmuneFactor": "#ffecd2",
                "DisuseFactor": "#e0bbe4",
                "ICD10Code": "#9575cd",
                "Synonym": "#b39ddb",
            }

            for record in node_records:
                node = record["n"]
                node_id = record["node_id"]
                labels = record["labels"]

                node_type = labels[0] if labels else "Entity"
                type_name = ENTITY_TYPE_EN_TO_ZH.get(node_type, node_type)
                color = NODE_COLOR_MAP.get(node_type, "#9c27ff")
                
                # 创建节点对象
                node_obj = {
                    "id": str(node_id),
                    "name": node.get("name", "未知节点"),
                    "category": node_type.lower(),
                    "symbolSize": 40 + (node.get("importance", 1) * 10),
                    "color": color,
                    "description": node.get("description", ""),
                    "relations": []
                }
                
                nodes.append(node_obj)
                node_ids.add(node_id)

            # 构建边查询（只查询已获取节点之间的关系）
            edge_query = """
            MATCH (a)-[r]->(b)
            WHERE id(a) IN $node_ids AND id(b) IN $node_ids
            RETURN id(a) as source, id(b) as target, type(r) as relation_type, properties(r) as properties
            """

            # 执行边查询
            edge_records = self.neo4j.execute_query(
                edge_query,
                {"node_ids": list(node_ids)}
            )

            # 构建边列表
            edges = []
            for record in edge_records:
                edge_obj = {
                    "source": str(record["source"]),
                    "target": str(record["target"]),
                    "relation": record["relation_type"],
                    "value": record["relation_type"]
                }
                edges.append(edge_obj)

            logger.info(f"获取到 {len(nodes)} 个节点和 {len(edges)} 条边")
            return nodes, edges

        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            import traceback
            traceback.print_exc()
            return [], []


# 示例用法
if __name__ == "__main__":
    import logging
    from db.neo4j_client import Neo4jClient

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("图检索器测试")
    print("=" * 60)

    with Neo4jClient() as client:
        # 创建检索器
        retriever = GraphRetriever(client)

        # 测试检索
        test_entities = ["重症急性胰腺炎", "剧烈腹痛"]
        results = retriever.retrieve(
            query="重症急性胰腺炎有哪些症状？",
            entity_names=test_entities,
            max_depth=2,
            limit=10
        )

        print(f"\n检索到 {len(results)} 个结果:")
        for i, result in enumerate(results):
            print(f"\n{i + 1}. {result.get('type', 'unknown')} - {result.get('name', 'N/A')}")
            print(f"   相关性: {result.get('relevance_score', 0):.2f}")

        # 格式化为上下文
        context = retriever.format_results_for_context(results)
        print(f"\n生成上下文 ({len(context)} 字符):")
        print(context[:500] + "..." if len(context) > 500 else context)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
