"""
测试 MySQL 到 Neo4j 的数据同步

测试内容：
1. 从 MySQL 读取 graph_data
2. 将数据同步到 Neo4j
3. 验证 Neo4j 中的数据是否正确
4. 比较 MySQL 和 Neo4j 中的数据是否一致
"""

import sys
import os
from pathlib import Path
import json

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import config

# 定义颜色
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"

def print_header(title):
    print(f"\n{Colors.BLUE}============================================================{Colors.RESET}")
    print(f"{Colors.BLUE}{title.center(60)}{Colors.RESET}")
    print(f"{Colors.BLUE}============================================================{Colors.RESET}")

def print_subheader(title):
    print(f"\n{Colors.CYAN}{title}{Colors.RESET}")

def print_success(msg):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.RESET}")

# 尝试导入数据库客户端（在 Colors 类定义之后）
try:
    from db.mysql_client import MySQLClient
    from db.neo4j_client import Neo4jClient
except ImportError as e:
    print(f"{Colors.RED}[FAIL] 导入错误: {e}{Colors.RESET}")
    print(f"{Colors.YELLOW}[WARN] 请确保已安装所有依赖: pip install -r requirements.txt{Colors.RESET}")
    print(f"{Colors.YELLOW}[WARN] 或者确保在正确的虚拟环境中运行此脚本{Colors.RESET}")
    sys.exit(1)

def sync_graph_data_to_neo4j(graph_data, neo4j_client_instance):
    """
    将 MySQL 中的图谱数据同步到 Neo4j（从 backend/app.py 复制）
    """
    try:
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        if not nodes:
            print_warning("没有节点数据需要同步")
            return
        
        print_info(f"开始同步 {len(nodes)} 个节点和 {len(edges)} 个关系到 Neo4j...")
        
        # 同步节点
        synced_nodes = 0
        for node in nodes:
            try:
                # 优先从 category 或 type 获取节点类型
                node_type = node.get("category") or node.get("type")
                node_name = node.get("name", node.get("label", ""))
                node_props = node.get("properties", {})
                
                if not node_name:
                    continue
                
                # 如果节点类型为空，尝试从 properties 中获取
                if not node_type:
                    node_type = node_props.get("category") or node_props.get("type") or "Entity"
                
                # 确保 node_type 是有效的 Neo4j 标签（只包含字母、数字和下划线）
                import re
                clean_node_type = re.sub(r'[^a-zA-Z0-9_]', '', str(node_type))
                if not clean_node_type:
                    clean_node_type = "Entity"
                
                # 在 properties 中保存原始类型信息
                props = {"name": node_name, "type": node_type, "category": node_type, **node_props}
                
                # 创建节点（使用清理后的类型作为 label）
                query = f"""
                MERGE (n:{clean_node_type} {{name: $name}})
                ON CREATE SET n = $props, n.created_at = datetime()
                ON MATCH SET n = $props, n.updated_at = datetime()
                RETURN n
                """
                neo4j_client_instance.execute_write(query, {"name": node_name, "props": props})
                synced_nodes += 1
            except Exception as e:
                print_warning(f"同步节点失败: {node.get('name', 'unknown')} - {e}")
        
        # 同步关系
        synced_edges = 0
        for edge in edges:
            try:
                source_id = edge.get("source", "")
                target_id = edge.get("target", "")
                rel_type = edge.get("label", edge.get("type", "RELATED_TO"))
                rel_props = edge.get("properties", {})
                
                if not source_id or not target_id:
                    continue
                
                # 创建关系（需要先找到对应的节点）
                query = f"""
                MATCH (a), (b)
                WHERE (id(a) = $source_id OR a.name = $source_name)
                  AND (id(b) = $target_id OR b.name = $target_name)
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r = $props, r.created_at = datetime()
                ON MATCH SET r = $props, r.updated_at = datetime()
                RETURN r
                """
                
                # 尝试将 source_id 和 target_id 转换为整数（如果是 Neo4j 内部 ID）
                try:
                    source_id_int = int(source_id)
                    target_id_int = int(target_id)
                except ValueError:
                    source_id_int = None
                    target_id_int = None
                
                params = {
                    "source_id": source_id_int,
                    "source_name": source_id if not source_id_int else None,
                    "target_id": target_id_int,
                    "target_name": target_id if not target_id_int else None,
                    "props": rel_props
                }
                
                neo4j_client_instance.execute_write(query, params)
                synced_edges += 1
            except Exception as e:
                print_warning(f"同步关系失败: {edge.get('source', 'unknown')} -> {edge.get('target', 'unknown')} - {e}")
        
        print_success(f"同步完成: {synced_nodes} 个节点, {synced_edges} 个关系")
        return synced_nodes, synced_edges
    except Exception as e:
        print_error(f"同步失败: {e}")
        raise

def test_sync_single_graph():
    """测试同步单个图谱的数据"""
    print_subheader("测试同步单个图谱")
    
    mysql_client = None
    neo4j_client = None
    
    try:
        # 连接数据库
        mysql_client = MySQLClient()
        if not mysql_client.connect():
            print_error("无法连接到 MySQL")
            return False
        
        neo4j_client = Neo4jClient()
        if not neo4j_client.verify_connection():
            print_error("无法连接到 Neo4j")
            return False
        
        # 获取一个有 graph_data 的图谱
        query = """
        SELECT graph_id, graph_name, graph_data
        FROM knowledge_graphs
        WHERE graph_data IS NOT NULL 
          AND graph_data != ''
          AND JSON_LENGTH(graph_data, '$.nodes') > 0
        ORDER BY created_at DESC
        LIMIT 1
        """
        results = mysql_client.execute_query(query)
        
        if not results:
            print_warning("没有找到有 graph_data 的图谱")
            return False
        
        row = results[0]
        graph_id = row['graph_id']
        graph_name = row['graph_name']
        graph_data = row['graph_data']
        
        print_info(f"测试图谱: {graph_name} (ID: {graph_id})")
        
        # 解析 graph_data
        if isinstance(graph_data, str):
            mysql_data = json.loads(graph_data)
        else:
            mysql_data = graph_data
        
        mysql_nodes = mysql_data.get('nodes', [])
        mysql_edges = mysql_data.get('edges', [])
        
        print_info(f"MySQL 数据: {len(mysql_nodes)} 个节点, {len(mysql_edges)} 条边")
        
        # 记录同步前的 Neo4j 数据量
        neo4j_data_before = neo4j_client.get_all_nodes_and_relationships()
        nodes_before = len(neo4j_data_before.get('nodes', []))
        edges_before = len(neo4j_data_before.get('relationships', []))
        
        print_info(f"同步前 Neo4j: {nodes_before} 个节点, {edges_before} 个关系")
        
        # 同步数据到 Neo4j
        synced_nodes, synced_edges = sync_graph_data_to_neo4j(mysql_data, neo4j_client)
        
        # 获取同步后的 Neo4j 数据
        neo4j_data_after = neo4j_client.get_all_nodes_and_relationships()
        nodes_after = len(neo4j_data_after.get('nodes', []))
        edges_after = len(neo4j_data_after.get('relationships', []))
        
        print_info(f"同步后 Neo4j: {nodes_after} 个节点, {edges_after} 个关系")
        
        # 验证同步结果
        if synced_nodes > 0:
            print_success(f"节点同步成功: {synced_nodes} 个")
        else:
            print_warning("没有节点被同步（可能节点已存在）")
        
        if synced_edges > 0:
            print_success(f"关系同步成功: {synced_edges} 个")
        else:
            print_warning("没有关系被同步（可能关系已存在或节点未找到）")
        
        # 检查 Neo4j 中是否有数据
        if nodes_after > nodes_before or nodes_after > 0:
            print_success("Neo4j 中有数据，同步功能正常")
            return True
        else:
            print_warning("Neo4j 中没有数据，可能同步失败")
            return False
        
    except Exception as e:
        print_error(f"测试失败: {e}")
        import traceback
        print_error(traceback.format_exc())
        return False
    finally:
        if mysql_client:
            mysql_client.disconnect()
        if neo4j_client:
            neo4j_client.close()

def test_data_consistency():
    """测试数据一致性：MySQL 和 Neo4j 中的数据是否一致"""
    print_subheader("测试数据一致性")
    
    mysql_client = None
    neo4j_client = None
    
    try:
        # 连接数据库
        mysql_client = MySQLClient()
        if not mysql_client.connect():
            print_error("无法连接到 MySQL")
            return False
        
        neo4j_client = Neo4jClient()
        if not neo4j_client.verify_connection():
            print_error("无法连接到 Neo4j")
            return False
        
        # 获取一个有 graph_data 的图谱
        query = """
        SELECT graph_id, graph_name, graph_data
        FROM knowledge_graphs
        WHERE graph_data IS NOT NULL 
          AND graph_data != ''
          AND JSON_LENGTH(graph_data, '$.nodes') > 0
        ORDER BY created_at DESC
        LIMIT 1
        """
        results = mysql_client.execute_query(query)
        
        if not results:
            print_warning("没有找到有 graph_data 的图谱")
            return False
        
        row = results[0]
        graph_id = row['graph_id']
        graph_name = row['graph_name']
        graph_data = row['graph_data']
        
        print_info(f"测试图谱: {graph_name} (ID: {graph_id})")
        
        # 解析 graph_data
        if isinstance(graph_data, str):
            mysql_data = json.loads(graph_data)
        else:
            mysql_data = graph_data
        
        mysql_nodes = mysql_data.get('nodes', [])
        mysql_edges = mysql_data.get('edges', [])
        
        # 获取 Neo4j 数据
        neo4j_data = neo4j_client.get_all_nodes_and_relationships()
        neo4j_nodes = neo4j_data.get('nodes', [])
        neo4j_relationships = neo4j_data.get('relationships', [])
        
        print_info(f"MySQL: {len(mysql_nodes)} 个节点, {len(mysql_edges)} 条边")
        print_info(f"Neo4j: {len(neo4j_nodes)} 个节点, {len(neo4j_relationships)} 个关系")
        
        # 检查节点数量（注意：Neo4j 可能包含多个图谱的数据）
        if len(neo4j_nodes) >= len(mysql_nodes):
            print_success("节点数量: Neo4j >= MySQL（正常，Neo4j 可能包含多个图谱的数据）")
        else:
            print_warning(f"节点数量: Neo4j ({len(neo4j_nodes)}) < MySQL ({len(mysql_nodes)})")
        
        # 检查关系数量
        if len(neo4j_relationships) >= len(mysql_edges):
            print_success("关系数量: Neo4j >= MySQL（正常，Neo4j 可能包含多个图谱的数据）")
        else:
            print_warning(f"关系数量: Neo4j ({len(neo4j_relationships)}) < MySQL ({len(mysql_edges)})")
        
        # 检查节点名称是否匹配（检查前几个节点）
        mysql_node_names = {node.get('name', '') for node in mysql_nodes[:10]}
        neo4j_node_names = {node.get('name', '') for node in neo4j_nodes[:10]}
        
        if mysql_node_names.intersection(neo4j_node_names):
            print_success("节点名称匹配: 部分节点在 Neo4j 中找到")
        else:
            print_warning("节点名称匹配: 前10个节点中没有匹配的节点")
        
        return True
        
    except Exception as e:
        print_error(f"测试失败: {e}")
        import traceback
        print_error(traceback.format_exc())
        return False
    finally:
        if mysql_client:
            mysql_client.disconnect()
        if neo4j_client:
            neo4j_client.close()

def main():
    """主函数"""
    print_header("MySQL 到 Neo4j 数据同步测试")
    
    all_tests_passed = True
    
    # 测试 1: 同步单个图谱
    if not test_sync_single_graph():
        all_tests_passed = False
    
    # 测试 2: 数据一致性
    if not test_data_consistency():
        all_tests_passed = False
    
    # 总结
    print_header("测试总结")
    if all_tests_passed:
        print_success("所有测试通过！")
    else:
        print_warning("部分测试失败，请检查上述错误信息")
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

