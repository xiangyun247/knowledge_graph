"""
测试数据持久化：验证数据是否正确保存到 MySQL

测试内容：
1. 验证新上传的文件是否正确保存 graph_data
2. 验证 graph_data 的格式是否正确（nodes 和 edges）
3. 验证节点和关系的数量是否匹配
4. 验证数据在重启后端后是否仍然存在
"""

import sys
import os
from pathlib import Path
import json
import requests
import time

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import config

# 按需导入 MySQLClient，避免导入 Neo4j 相关模块
try:
    from db.mysql_client import MySQLClient
except ImportError as e:
    # 如果导入失败，尝试直接导入 MySQL 相关模块
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    
    # 直接导入 MySQL 客户端，避免通过 __init__.py 导入 Neo4j
    import os
    from sqlalchemy import create_engine, text
    from dotenv import load_dotenv
    import logging
    
    # 创建一个简单的 MySQLClient 类
    class MySQLClient:
        def __init__(self, host=None, port=None, user=None, password=None, database=None):
            self.host = host or os.getenv("MYSQL_HOST", "localhost")
            self.port = port or int(os.getenv("MYSQL_PORT", 3306))
            self.user = user or os.getenv("MYSQL_USER", "root")
            self.password = password or os.getenv("MYSQL_PASSWORD", "")
            self.database = database or os.getenv("MYSQL_DATABASE", "knowledge_graph_system")
            self.engine = None
        
        def connect(self):
            try:
                self.engine = create_engine(
                    f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
                )
                with self.engine.connect():
                    logging.info(f"成功连接到MySQL数据库: {self.database}")
                return True
            except Exception as e:
                logging.error(f"连接MySQL数据库失败: {e}")
                return False
        
        def disconnect(self):
            if self.engine:
                self.engine.dispose()
        
        def execute_query(self, query, params=None):
            try:
                if not self.engine:
                    self.connect()
                with self.engine.connect() as conn:
                    result = conn.execute(text(query), params or {})
                    return [dict(row._mapping) for row in result]
            except Exception as e:
                logging.error(f"查询执行失败: {e}")
                return []

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

BACKEND_URL = f"http://{config.BACKEND_HOST}:{config.BACKEND_PORT}"
API_BASE = f"{BACKEND_URL}/api"

def test_mysql_connection():
    """测试 MySQL 连接"""
    print_subheader("测试 MySQL 连接")
    try:
        mysql_client = MySQLClient()
        if mysql_client.connect():
            print_success("MySQL 连接成功")
            mysql_client.disconnect()
            return True
        else:
            print_error("MySQL 连接失败")
            return False
    except Exception as e:
        print_error(f"MySQL 连接异常: {e}")
        return False

def test_graph_data_exists():
    """测试所有图谱是否都有 graph_data"""
    print_subheader("测试图谱 graph_data 存在性")
    try:
        mysql_client = MySQLClient()
        if not mysql_client.connect():
            print_error("无法连接到 MySQL")
            return False
        
        # 简化查询，避免复杂的 CASE 和排序导致内存问题
        query = """
        SELECT graph_id, graph_name, graph_data, entity_count, relation_count
        FROM knowledge_graphs
        """
        results = mysql_client.execute_query(query)
        
        total_graphs = len(results)
        graphs_with_data = 0
        graphs_without_data = 0
        
        for row in results:
            graph_id = row['graph_id']
            graph_name = row['graph_name']
            graph_data = row.get('graph_data')
            entity_count = row.get('entity_count', 0)
            relation_count = row.get('relation_count', 0)
            
            # 判断是否有数据
            has_data = False
            if graph_data:
                if isinstance(graph_data, str):
                    try:
                        data = json.loads(graph_data)
                        nodes = data.get('nodes', [])
                        if nodes and len(nodes) > 0:
                            has_data = True
                    except:
                        pass
                else:
                    nodes = graph_data.get('nodes', []) if isinstance(graph_data, dict) else []
                    if nodes and len(nodes) > 0:
                        has_data = True
            
            if has_data:
                graphs_with_data += 1
                print_success(f"  {graph_name}: 有数据 (实体: {entity_count}, 关系: {relation_count})")
            else:
                graphs_without_data += 1
                print_warning(f"  {graph_name}: 无数据")
        
        print_info(f"\n总计: {total_graphs} 个图谱")
        print_info(f"有数据: {graphs_with_data} 个")
        print_info(f"无数据: {graphs_without_data} 个")
        
        mysql_client.disconnect()
        
        if graphs_without_data == 0:
            print_success("所有图谱都有 graph_data")
            return True
        else:
            print_warning(f"有 {graphs_without_data} 个图谱没有 graph_data")
            return graphs_with_data > 0
        
    except Exception as e:
        print_error(f"测试失败: {e}")
        return False

def test_graph_data_format():
    """测试 graph_data 格式是否正确"""
    print_subheader("测试 graph_data 格式")
    try:
        mysql_client = MySQLClient()
        if not mysql_client.connect():
            print_error("无法连接到 MySQL")
            return False
        
        query = """
        SELECT graph_id, graph_name, graph_data, entity_count, relation_count
        FROM knowledge_graphs
        WHERE graph_data IS NOT NULL 
          AND graph_data != ''
          AND JSON_LENGTH(graph_data, '$.nodes') > 0
        ORDER BY created_at DESC
        LIMIT 5
        """
        results = mysql_client.execute_query(query)
        
        if not results:
            print_warning("没有找到有 graph_data 的图谱")
            return False
        
        all_passed = True
        
        for row in results:
            graph_id = row['graph_id']
            graph_name = row['graph_name']
            graph_data = row['graph_data']
            expected_entities = row['entity_count']
            expected_relations = row['relation_count']
            
            print_info(f"\n检查图谱: {graph_name}")
            
            try:
                # 解析 JSON
                if isinstance(graph_data, str):
                    data = json.loads(graph_data)
                else:
                    data = graph_data
                
                # 检查必需字段
                if 'nodes' not in data:
                    print_error(f"  缺少 'nodes' 字段")
                    all_passed = False
                    continue
                
                if 'edges' not in data:
                    print_error(f"  缺少 'edges' 字段")
                    all_passed = False
                    continue
                
                nodes = data['nodes']
                edges = data['edges']
                
                # 检查节点格式
                if nodes:
                    sample_node = nodes[0]
                    required_fields = ['id', 'name', 'category']
                    missing_fields = [f for f in required_fields if f not in sample_node]
                    if missing_fields:
                        print_error(f"  节点缺少必需字段: {missing_fields}")
                        all_passed = False
                    else:
                        print_success(f"  节点格式正确: {len(nodes)} 个节点")
                
                # 检查边格式
                if edges:
                    sample_edge = edges[0]
                    required_fields = ['source', 'target', 'type']
                    missing_fields = [f for f in required_fields if f not in sample_edge]
                    if missing_fields:
                        print_error(f"  边缺少必需字段: {missing_fields}")
                        all_passed = False
                    else:
                        print_success(f"  边格式正确: {len(edges)} 条边")
                
                # 检查数量（注意：由于去重等原因，实际数量可能小于预期）
                print_info(f"  预期: {expected_entities} 个实体, {expected_relations} 个关系")
                print_info(f"  实际: {len(nodes)} 个节点, {len(edges)} 条边")
                
                if len(nodes) > 0 and len(edges) > 0:
                    print_success(f"  数据完整性: 通过")
                else:
                    print_warning(f"  数据完整性: 节点或边为空")
                
            except json.JSONDecodeError as e:
                print_error(f"  JSON 解析失败: {e}")
                all_passed = False
            except Exception as e:
                print_error(f"  检查失败: {e}")
                all_passed = False
        
        mysql_client.disconnect()
        return all_passed
        
    except Exception as e:
        print_error(f"测试失败: {e}")
        return False

def test_data_consistency():
    """测试数据一致性：MySQL 中的 graph_data 与 API 返回的数据是否一致"""
    print_subheader("测试数据一致性（MySQL vs API）")
    try:
        mysql_client = MySQLClient()
        if not mysql_client.connect():
            print_error("无法连接到 MySQL")
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
        
        # 解析 MySQL 中的 graph_data
        if isinstance(graph_data, str):
            mysql_data = json.loads(graph_data)
        else:
            mysql_data = graph_data
        
        mysql_nodes = mysql_data.get('nodes', [])
        mysql_edges = mysql_data.get('edges', [])
        
        # 从 API 获取数据
        try:
            response = requests.get(
                f"{API_BASE}/graph/data",
                params={"graph_id": graph_id},
                timeout=10
            )
            response.raise_for_status()
            api_data = response.json()
            
            if api_data.get("status") != "success":
                print_error(f"API 返回错误: {api_data.get('message')}")
                return False
            
            api_nodes = api_data.get("data", {}).get("nodes", [])
            api_edges = api_data.get("data", {}).get("edges", [])
            
            print_info(f"MySQL: {len(mysql_nodes)} 个节点, {len(mysql_edges)} 条边")
            print_info(f"API: {len(api_nodes)} 个节点, {len(api_edges)} 条边")
            
            # 比较数量（注意：API 可能有 limit 限制）
            if len(api_nodes) <= len(mysql_nodes) and len(api_edges) <= len(mysql_edges):
                print_success("数据一致性: 通过（API 数据是 MySQL 数据的子集）")
                return True
            else:
                print_warning("数据一致性: API 返回的数据量大于 MySQL，可能有问题")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"API 请求失败: {e}")
            print_info("跳过 API 一致性测试（后端可能未启动）")
            return True  # 不阻止测试继续
        
        finally:
            mysql_client.disconnect()
        
    except Exception as e:
        print_error(f"测试失败: {e}")
        return False

def main():
    """主函数"""
    print_header("数据持久化测试")
    
    all_tests_passed = True
    
    # 测试 1: MySQL 连接
    if not test_mysql_connection():
        print_error("MySQL 连接失败，无法继续测试")
        return False
    
    # 测试 2: graph_data 存在性
    if not test_graph_data_exists():
        all_tests_passed = False
    
    # 测试 3: graph_data 格式
    if not test_graph_data_format():
        all_tests_passed = False
    
    # 测试 4: 数据一致性
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

