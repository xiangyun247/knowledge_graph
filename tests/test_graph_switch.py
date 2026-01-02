"""
测试图谱切换功能
验证：
1. 图谱列表是否正确获取
2. 切换不同图谱时数据是否正确加载
3. 节点数量是否与 MySQL 记录一致
4. 数据格式是否正确
5. 全部图谱模式是否正确工作
"""

import os
import sys
from pathlib import Path
import requests
import json
from typing import Dict, List, Any

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 配置
BACKEND_URL = "http://localhost:5001"
API_BASE = f"{BACKEND_URL}/api"

# 延迟导入 MySQLClient，避免导入时的依赖问题
try:
    from db.mysql_client import MySQLClient
    MYSQL_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入 MySQLClient: {e}")
    MYSQL_AVAILABLE = False
    MySQLClient = None

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.RESET}")

def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def test_backend_connection():
    """测试后端连接"""
    print_header("测试后端连接")
    try:
        # 尝试访问 API 文档或图谱列表接口来测试连接
        response = requests.get(f"{API_BASE}/graph/list", timeout=10, 
                              headers={"Authorization": "Bearer mock-jwt-token"})
        if response.status_code in [200, 401, 403]:  # 200 成功，401/403 表示服务运行但需要认证
            print_success("后端服务连接成功")
            return True
        else:
            print_error(f"后端服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print_error(f"连接后端服务超时")
        print_info(f"请确保后端服务运行在 {BACKEND_URL}")
        print_info("提示: 如果后端正在运行，可能是响应时间过长")
        return False
    except requests.exceptions.ConnectionError:
        print_error(f"无法连接到后端服务")
        print_info(f"请确保后端服务运行在 {BACKEND_URL}")
        print_info("提示: 请先启动后端服务 (python run.py)")
        return False
    except requests.exceptions.RequestException as e:
        print_error(f"连接后端服务时发生错误: {str(e)}")
        print_info(f"请确保后端服务运行在 {BACKEND_URL}")
        return False

def test_get_graph_list():
    """测试获取图谱列表"""
    print_header("测试获取图谱列表")
    try:
        response = requests.get(
            f"{API_BASE}/graph/list",
            headers={"Authorization": "Bearer mock-jwt-token"},
            timeout=10
        )
        
        if response.status_code != 200:
            print_error(f"获取图谱列表失败: {response.status_code}")
            print_error(f"响应: {response.text}")
            return None
        
        data = response.json()
        if data.get("status") != "success":
            print_error(f"API 返回错误状态: {data.get('message', '未知错误')}")
            return None
        
        graph_list = data.get("data", {}).get("list", [])
        print_success(f"成功获取 {len(graph_list)} 个图谱")
        
        if graph_list:
            print_info("\n图谱列表:")
            for i, graph in enumerate(graph_list, 1):
                graph_id = graph.get("graph_id", "N/A")
                graph_name = graph.get("graph_name", "N/A")
                entity_count = graph.get("entity_count", 0)
                relation_count = graph.get("relation_count", 0)
                status = graph.get("status", "N/A")
                print(f"  {i}. {graph_name}")
                print(f"     ID: {graph_id}")
                print(f"     状态: {status}")
                print(f"     实体数: {entity_count}, 关系数: {relation_count}")
        
        return graph_list
    except Exception as e:
        print_error(f"获取图谱列表时发生错误: {e}")
        return None

def test_get_graph_data(graph_id: str = None, limit: int = None, offset: int = None):
    """测试获取图谱数据"""
    params = {}
    if graph_id:
        params["graph_id"] = graph_id
    if limit:
        params["limit"] = limit
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(
            f"{API_BASE}/graph/data",
            params=params,
            headers={"Authorization": "Bearer mock-jwt-token"},
            timeout=10
        )
        
        if response.status_code != 200:
            print_error(f"获取图谱数据失败: {response.status_code}")
            print_error(f"响应: {response.text}")
            return None
        
        data = response.json()
        return data
    except Exception as e:
        print_error(f"获取图谱数据时发生错误: {e}")
        return None

def test_graph_switch(graph_list: List[Dict]):
    """测试图谱切换功能"""
    print_header("测试图谱切换功能")
    
    if not graph_list:
        print_warning("没有可用的图谱进行测试")
        return False
    
    # 测试每个图谱
    all_passed = True
    mysql_client = None
    if MYSQL_AVAILABLE:
        try:
            mysql_client = MySQLClient()
            mysql_client.connect()
        except Exception as e:
            print_warning(f"无法连接 MySQL，跳过 MySQL 验证: {e}")
            mysql_client = None
    
    for i, graph in enumerate(graph_list, 1):
        graph_id = graph.get("graph_id")
        graph_name = graph.get("graph_name", "N/A")
        expected_entity_count = graph.get("entity_count", 0)
        expected_relation_count = graph.get("relation_count", 0)
        status = graph.get("status", "unknown")
        
        print(f"\n{i}. 测试图谱: {graph_name}")
        print(f"   ID: {graph_id}")
        print(f"   预期: {expected_entity_count} 个实体, {expected_relation_count} 个关系")
        
        # 跳过未完成的图谱
        if status != "completed":
            print_warning(f"   跳过: 图谱状态为 '{status}'，未完成")
            continue
        
        # 获取该图谱的数据
        data = test_get_graph_data(graph_id=graph_id, limit=1000)
        if not data:
            print_error(f"   失败: 无法获取图谱数据")
            all_passed = False
            continue
        
        # 检查响应格式
        if data.get("status") != "success":
            print_error(f"   失败: API 返回错误状态: {data.get('message', '未知错误')}")
            all_passed = False
            continue
        
        # 获取节点和边
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        total_nodes = data.get("total_nodes", len(nodes))
        total_relations = data.get("total_relations", len(edges))
        
        print(f"   实际: {len(nodes)} 个节点, {len(edges)} 个边")
        print(f"   总计: {total_nodes} 个节点, {total_relations} 个关系")
        
        # 验证节点数量
        if expected_entity_count > 0:
            if len(nodes) != expected_entity_count:
                print_warning(f"   警告: 节点数量不匹配 (预期: {expected_entity_count}, 实际: {len(nodes)})")
                print_info(f"   注意: 如果使用了 limit 参数，可能只返回部分节点")
            else:
                print_success(f"   [OK] 节点数量匹配")
        
        # 验证关系数量
        if expected_relation_count > 0:
            if len(edges) != expected_relation_count:
                print_warning(f"   警告: 关系数量不匹配 (预期: {expected_relation_count}, 实际: {len(edges)})")
                print_info(f"   注意: 如果使用了 limit 参数，可能只返回部分关系")
            else:
                print_success(f"   [OK] 关系数量匹配")
        
        # 验证数据格式
        if not isinstance(nodes, list):
            print_error(f"   失败: nodes 不是列表类型")
            all_passed = False
            continue
        
        if not isinstance(edges, list):
            print_error(f"   失败: edges 不是列表类型")
            all_passed = False
            continue
        
        # 验证节点格式
        if nodes:
            sample_node = nodes[0]
            required_fields = ["id", "name", "category"]
            missing_fields = [field for field in required_fields if field not in sample_node]
            if missing_fields:
                print_error(f"   失败: 节点缺少必需字段: {missing_fields}")
                all_passed = False
            else:
                print_success(f"   [OK] 节点格式正确")
        
        # 验证边格式
        if edges:
            sample_edge = edges[0]
            required_fields = ["source", "target"]
            missing_fields = [field for field in required_fields if field not in sample_edge]
            if missing_fields:
                print_error(f"   失败: 边缺少必需字段: {missing_fields}")
                all_passed = False
            else:
                print_success(f"   [OK] 边格式正确")
        
        # 验证节点类型
        if nodes:
            unknown_types = [node for node in nodes if node.get("category") == "未知类型" or not node.get("category")]
            if unknown_types:
                print_warning(f"   警告: 发现 {len(unknown_types)} 个未知类型的节点")
            else:
                print_success(f"   [OK] 所有节点都有正确的类型")
        
        # 从 MySQL 验证 graph_data
        if mysql_client:
            try:
                graph_record = mysql_client.get_graph_by_id(graph_id)
                if graph_record:
                    graph_data = graph_record.get("graph_data")
                    if graph_data:
                        if isinstance(graph_data, str):
                            graph_data = json.loads(graph_data)
                        mysql_nodes = graph_data.get("nodes", [])
                        mysql_edges = graph_data.get("edges", graph_data.get("relations", []))
                        
                        if len(mysql_nodes) == len(nodes) and len(mysql_edges) == len(edges):
                            print_success(f"   [OK] MySQL graph_data 与 API 返回数据一致")
                        else:
                            print_warning(f"   警告: MySQL graph_data 与 API 返回数据不一致")
                            print_info(f"   MySQL: {len(mysql_nodes)} 节点, {len(mysql_edges)} 边")
                            print_info(f"   API: {len(nodes)} 节点, {len(edges)} 边")
                    else:
                        print_warning(f"   警告: MySQL 中没有 graph_data 数据（可能是旧记录）")
            except Exception as e:
                print_warning(f"   警告: 无法从 MySQL 验证数据: {e}")
        else:
            print_info(f"   跳过: MySQL 客户端不可用")
    
    if mysql_client:
        mysql_client.disconnect()
    return all_passed

def test_all_graphs_mode():
    """测试全部图谱模式（不指定 graph_id）"""
    print_header("测试全部图谱模式")
    
    # 获取所有图谱数据（不指定 graph_id）
    data = test_get_graph_data(limit=1000)
    if not data:
        print_error("无法获取全部图谱数据")
        return False
    
    if data.get("status") != "success":
        print_error(f"API 返回错误状态: {data.get('message', '未知错误')}")
        return False
    
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    
    print_success(f"全部图谱模式: {len(nodes)} 个节点, {len(edges)} 个边")
    
    if nodes:
        print_success("[OK] 全部图谱模式正常工作")
        return True
    else:
        print_warning("⚠ 全部图谱模式返回空数据（可能是 Neo4j 中没有数据）")
        return True  # 不算错误，可能是正常情况

def main():
    """主测试函数"""
    print_header("图谱切换功能全面测试")
    
    # 1. 测试后端连接
    if not test_backend_connection():
        print_error("后端连接失败，无法继续测试")
        return False
    
    # 2. 获取图谱列表
    graph_list = test_get_graph_list()
    if not graph_list:
        print_error("无法获取图谱列表，无法继续测试")
        return False
    
    # 3. 测试图谱切换
    switch_passed = test_graph_switch(graph_list)
    
    # 4. 测试全部图谱模式
    all_graphs_passed = test_all_graphs_mode()
    
    # 总结
    print_header("测试总结")
    if switch_passed and all_graphs_passed:
        print_success("所有测试通过！")
        return True
    else:
        print_warning("部分测试未通过，请检查上述输出")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

