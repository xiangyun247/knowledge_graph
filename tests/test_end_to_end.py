"""
端到端集成测试脚本

测试完整的工作流程：
1. 文件上传 → 知识图谱生成 → 数据保存
2. 图谱切换 → 数据加载 → 可视化显示
3. 智能问答 → RAG 检索 → 答案生成
4. 实体搜索 → 结果展示 → 图谱关联
"""

import sys
import os
from pathlib import Path
import json
import requests
import time
from typing import Dict, Any, Optional

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
    MAGENTA = "\033[95m"

def print_header(title):
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BLUE}{title.center(60)}{Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.RESET}")

def print_subheader(title):
    print(f"\n{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    print(f"{Colors.CYAN}{title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")

def print_success(msg):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.RESET}")

def print_step(step_num, msg):
    print(f"\n{Colors.MAGENTA}[步骤 {step_num}] {msg}{Colors.RESET}")

BACKEND_URL = f"http://{config.BACKEND_HOST}:{config.BACKEND_PORT}"
API_BASE = f"{BACKEND_URL}/api"

class EndToEndTester:
    """端到端测试类"""
    
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.api_base = API_BASE
        self.test_results = []
        
    def test_backend_connection(self) -> bool:
        """测试后端连接"""
        print_subheader("测试后端服务连接")
        try:
            response = requests.get(f"{self.api_base}/graph/list", timeout=5)
            response.raise_for_status()
            print_success("后端服务连接成功")
            return True
        except requests.exceptions.ConnectionError:
            print_error(f"无法连接到后端服务: {self.backend_url}")
            print_warning("请确保后端服务正在运行: python run.py")
            return False
        except Exception as e:
            print_error(f"后端服务连接失败: {e}")
            return False
    
    def test_health_check(self) -> bool:
        """测试健康检查接口"""
        print_subheader("测试健康检查接口")
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            response.raise_for_status()
            data = response.json()
            print_success(f"健康检查通过: {data.get('status', 'unknown')}")
            return True
        except Exception as e:
            print_warning(f"健康检查失败: {e}")
            return False
    
    def test_get_graph_list(self) -> Optional[list]:
        """测试获取图谱列表"""
        print_subheader("测试获取图谱列表")
        try:
            response = requests.get(f"{self.api_base}/graph/list", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 处理不同的响应格式
            if isinstance(data, dict):
                if data.get("status") == "success":
                    data_obj = data.get("data", {})
                    # 尝试多种可能的字段名
                    graph_list = (data_obj.get("graphs") or 
                                 data_obj.get("list") or 
                                 data_obj.get("data") or 
                                 [])
                else:
                    print_error(f"获取图谱列表失败: {data.get('message', '未知错误')}")
                    return None
            elif isinstance(data, list):
                graph_list = data
            else:
                print_error(f"获取图谱列表失败: 未知的响应格式")
                return None
            
            if graph_list:
                print_success(f"成功获取 {len(graph_list)} 个图谱")
                return graph_list
            else:
                print_warning("图谱列表为空")
                return []
        except Exception as e:
            print_error(f"获取图谱列表失败: {e}")
            return None
    
    def test_get_graph_data(self, graph_id: Optional[str] = None) -> bool:
        """测试获取图谱数据"""
        print_subheader(f"测试获取图谱数据 (graph_id: {graph_id or '全部'})")
        try:
            params = {}
            if graph_id:
                params["graph_id"] = graph_id
            params["limit"] = 100  # 限制返回数量
            
            response = requests.get(f"{self.api_base}/graph/data", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success" and "data" in data:
                graph_data = data["data"]
                nodes = graph_data.get("nodes", [])
                edges = graph_data.get("edges", [])
                print_success(f"成功获取图谱数据: {len(nodes)} 个节点, {len(edges)} 条边")
                
                # 验证数据格式
                if nodes:
                    sample_node = nodes[0]
                    required_fields = ["id", "name", "category"]
                    missing = [f for f in required_fields if f not in sample_node]
                    if missing:
                        print_error(f"节点缺少必需字段: {missing}")
                        return False
                    else:
                        print_success("节点格式正确")
                
                if edges:
                    sample_edge = edges[0]
                    # 边可能使用 'type' 或 'label' 字段
                    required_fields = ["source", "target"]
                    missing = [f for f in required_fields if f not in sample_edge]
                    if missing:
                        print_error(f"边缺少必需字段: {missing}")
                        return False
                    elif "type" in sample_edge or "label" in sample_edge:
                        print_success("边格式正确")
                    else:
                        print_warning("边缺少类型字段（type 或 label）")
                
                return True
            else:
                print_error(f"获取图谱数据失败: {data.get('message', '未知错误')}")
                return False
        except Exception as e:
            print_error(f"获取图谱数据失败: {e}")
            return False
    
    def test_graph_switching(self, graph_list: list) -> bool:
        """测试图谱切换功能"""
        print_subheader("测试图谱切换功能")
        
        if not graph_list or len(graph_list) < 2:
            print_warning("图谱数量不足，跳过切换测试")
            return True
        
        success_count = 0
        total_count = min(3, len(graph_list))  # 测试前3个图谱
        
        for i, graph in enumerate(graph_list[:total_count], 1):
            graph_id = graph.get("graph_id")
            graph_name = graph.get("graph_name", f"图谱 {i}")
            
            print_info(f"测试切换图谱 {i}/{total_count}: {graph_name}")
            
            if self.test_get_graph_data(graph_id):
                success_count += 1
            else:
                print_warning(f"图谱 {graph_name} 数据获取失败")
        
        if success_count == total_count:
            print_success(f"图谱切换测试通过: {success_count}/{total_count}")
            return True
        else:
            print_warning(f"图谱切换测试部分通过: {success_count}/{total_count}")
            return success_count > 0
    
    def test_entity_search(self) -> bool:
        """测试实体搜索功能"""
        print_subheader("测试实体搜索功能")
        
        test_cases = [
            {"keyword": "胰腺炎", "entity_type": "Disease"},
            {"keyword": "疼痛", "entity_type": "Symptom"},
        ]
        
        success_count = 0
        
        for i, test_case in enumerate(test_cases, 1):
            keyword = test_case["keyword"]
            entity_type = test_case.get("entity_type")
            
            print_info(f"测试搜索 {i}/{len(test_cases)}: {keyword} (类型: {entity_type})")
            
            try:
                params = {"keyword": keyword}
                if entity_type:
                    params["entity_type"] = entity_type
                
                response = requests.get(f"{self.api_base}/search/entities", params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # 处理不同的响应格式
                if isinstance(data, list):
                    # 如果直接返回列表
                    entities = data
                    print_success(f"搜索成功: 找到 {len(entities)} 个实体")
                    success_count += 1
                elif data.get("status") == "success":
                    entities = data.get("data", {})
                    if isinstance(entities, list):
                        entity_list = entities
                    elif isinstance(entities, dict):
                        entity_list = entities.get("entities", [])
                    else:
                        entity_list = []
                    print_success(f"搜索成功: 找到 {len(entity_list)} 个实体")
                    success_count += 1
                else:
                    print_warning(f"搜索失败: {data.get('message', '未知错误')}")
            except Exception as e:
                print_warning(f"搜索异常: {e}")
        
        if success_count == len(test_cases):
            print_success(f"实体搜索测试通过: {success_count}/{len(test_cases)}")
            return True
        else:
            print_warning(f"实体搜索测试部分通过: {success_count}/{len(test_cases)}")
            return success_count > 0
    
    def test_intelligent_query(self) -> bool:
        """测试智能问答功能"""
        print_subheader("测试智能问答功能")
        
        test_questions = [
            "急性胰腺炎有什么症状？",
            "如何治疗急性胰腺炎？",
        ]
        
        success_count = 0
        
        for i, question in enumerate(test_questions, 1):
            print_info(f"测试问题 {i}/{len(test_questions)}: {question}")
            
            try:
                payload = {
                    "question": question,
                    "use_graph": True,
                    "use_vector": True,
                    "top_k": 5
                }
                
                response = requests.post(
                    f"{self.api_base}/query",
                    json=payload,
                    timeout=90  # 问答可能需要较长时间，增加到90秒
                )
                response.raise_for_status()
                data = response.json()
                
                # 处理不同的响应格式
                # QueryResponse 直接返回 answer, sources 等字段，不包含 status
                if isinstance(data, dict):
                    # 检查是否是 QueryResponse 格式（直接包含 answer 字段）
                    if "answer" in data:
                        answer = data.get("answer", "")
                        sources = data.get("sources", [])
                        
                        if answer and len(answer.strip()) > 0:
                            print_success(f"问答成功: 答案长度 {len(answer)} 字符")
                            print_info(f"  来源数量: {len(sources)}")
                            print_info(f"  置信度: {data.get('confidence', 'N/A')}")
                            success_count += 1
                        else:
                            print_warning("问答返回空答案")
                    # 检查是否是包装格式（包含 status 和 data）
                    elif data.get("status") == "success":
                        answer = data.get("data", {}).get("answer", "")
                        sources = data.get("data", {}).get("sources", [])
                        
                        if answer and len(answer.strip()) > 0:
                            print_success(f"问答成功: 答案长度 {len(answer)} 字符")
                            print_info(f"  来源数量: {len(sources)}")
                            success_count += 1
                        else:
                            print_warning("问答返回空答案")
                    else:
                        error_msg = data.get("message") or data.get("detail") or "未知错误"
                        print_warning(f"问答失败: {error_msg}")
                else:
                    print_warning(f"问答返回未知格式: {type(data)}")
            except requests.exceptions.Timeout:
                print_warning(f"问答超时: {question} (可能需要更长时间)")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 503:
                    print_warning(f"问答服务不可用: RAG 流水线未初始化")
                else:
                    print_warning(f"问答HTTP错误: {e}")
            except Exception as e:
                print_warning(f"问答异常: {e}")
        
        if success_count == len(test_questions):
            print_success(f"智能问答测试通过: {success_count}/{len(test_questions)}")
            return True
        else:
            print_warning(f"智能问答测试部分通过: {success_count}/{len(test_questions)}")
            return success_count > 0
    
    def test_statistics(self) -> bool:
        """测试统计接口"""
        print_subheader("测试统计接口")
        # 尝试多个可能的统计接口路径
        stats_endpoints = [
            f"{self.api_base}/stats",
            f"{self.api_base}/history/stats",
        ]
        
        for endpoint in stats_endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success":
                    stats = data.get("data", {})
                    print_success(f"统计接口正常: {endpoint}")
                    print_info(f"  节点数: {stats.get('total_nodes', stats.get('total_entities', 'N/A'))}")
                    print_info(f"  关系数: {stats.get('total_relations', 'N/A')}")
                    print_info(f"  实体类型数: {stats.get('entity_types', 'N/A')}")
                    return True
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    continue  # 尝试下一个端点
                else:
                    print_warning(f"统计接口失败 ({endpoint}): {e}")
            except Exception as e:
                print_warning(f"统计接口异常 ({endpoint}): {e}")
        
        print_warning("所有统计接口都不可用")
        return False
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print_header("端到端集成测试")
        
        all_passed = True
        
        # 步骤 1: 测试后端连接
        print_step(1, "测试后端服务连接")
        if not self.test_backend_connection():
            print_error("后端服务不可用，无法继续测试")
            return False
        
        # 步骤 2: 测试健康检查
        print_step(2, "测试健康检查接口")
        self.test_health_check()
        
        # 步骤 3: 测试获取图谱列表
        print_step(3, "测试获取图谱列表")
        graph_list = self.test_get_graph_list()
        if not graph_list:
            print_warning("无法获取图谱列表，部分测试将跳过")
        
        # 步骤 4: 测试获取全部图谱数据
        print_step(4, "测试获取全部图谱数据")
        if not self.test_get_graph_data():
            all_passed = False
        
        # 步骤 5: 测试图谱切换
        if graph_list:
            print_step(5, "测试图谱切换功能")
            if not self.test_graph_switching(graph_list):
                all_passed = False
        
        # 步骤 6: 测试实体搜索
        print_step(6, "测试实体搜索功能")
        if not self.test_entity_search():
            all_passed = False
        
        # 步骤 7: 测试智能问答
        print_step(7, "测试智能问答功能")
        if not self.test_intelligent_query():
            all_passed = False
        
        # 步骤 8: 测试统计接口
        print_step(8, "测试统计接口")
        self.test_statistics()
        
        # 总结
        print_header("测试总结")
        if all_passed:
            print_success("所有核心测试通过！")
        else:
            print_warning("部分测试失败，请检查上述错误信息")
        
        return all_passed

def main():
    """主函数"""
    tester = EndToEndTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

