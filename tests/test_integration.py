"""
前后端集成测试脚本
测试前后端交互和主要功能
"""
import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置
BACKEND_URL = "http://localhost:5001"
FRONTEND_URL = "http://localhost:5002"  # 前端运行端口

def print_section(title):
    """打印测试章节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_backend_apis():
    """测试后端主要 API 接口"""
    print_section("测试后端 API 接口")
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # 1. 测试实体搜索
    print("\n[1] 测试实体搜索接口...")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/search/entities",
            params={"keyword": "胰腺炎", "limit": 10},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('data', []))
            print(f"   [OK] 搜索成功，返回 {count} 个结果")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 2. 测试图谱数据
    print("\n[2] 测试知识图谱数据接口...")
    results["total"] += 1
    try:
        response = requests.get(f"{BACKEND_URL}/api/graph/data", timeout=5)
        if response.status_code == 200:
            data = response.json()
            nodes = len(data.get('nodes', []))
            edges = len(data.get('edges', []))
            print(f"   [OK] 图谱数据正常，节点: {nodes}, 边: {edges}")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 3. 测试历史记录列表
    print("\n[3] 测试历史记录接口...")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/history/list",
            params={"page": 1, "page_size": 10},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('data', []))
            print(f"   [OK] 历史记录查询成功，返回 {count} 条记录")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 4. 测试知识图谱列表
    print("\n[4] 测试知识图谱列表接口...")
    results["total"] += 1
    try:
        response = requests.get(f"{BACKEND_URL}/api/kg/list", timeout=5)
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('data', []))
            print(f"   [OK] 图谱列表查询成功，返回 {count} 个图谱")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 5. 测试图谱实体搜索
    print("\n[5] 测试图谱实体搜索接口...")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/graph/entities/search",
            params={"keyword": "疾病", "entity_type": "Disease", "limit": 5},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('data', []))
            print(f"   [OK] 图谱实体搜索成功，返回 {count} 个结果")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    return results

def test_frontend_access():
    """测试前端访问"""
    print_section("测试前端访问")
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # 测试前端首页
    print("\n[1] 测试前端首页...")
    results["total"] += 1
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print(f"   [OK] 前端首页可访问")
            results["passed"] += 1
        else:
            print(f"   [WARN] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] 无法访问前端: {e}")
        print(f"   请确保前端服务运行在 {FRONTEND_URL}")
        results["failed"] += 1
    
    return results

def test_cors():
    """测试 CORS 跨域配置"""
    print_section("测试 CORS 跨域配置")
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    print("\n[1] 测试 CORS 头信息...")
    results["total"] += 1
    try:
        response = requests.options(
            f"{BACKEND_URL}/api/search/entities",
            headers={
                "Origin": FRONTEND_URL,
                "Access-Control-Request-Method": "GET"
            },
            timeout=5
        )
        cors_headers = {
            "access-control-allow-origin": response.headers.get("Access-Control-Allow-Origin"),
            "access-control-allow-methods": response.headers.get("Access-Control-Allow-Methods"),
        }
        
        if cors_headers["access-control-allow-origin"]:
            print(f"   [OK] CORS 配置正常")
            print(f"   Allow-Origin: {cors_headers['access-control-allow-origin']}")
            results["passed"] += 1
        else:
            print(f"   [WARN] 未检测到 CORS 头信息")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    return results

def print_summary(backend_results, frontend_results, cors_results):
    """打印测试总结"""
    print_section("测试总结")
    
    total_passed = backend_results["passed"] + frontend_results["passed"] + cors_results["passed"]
    total_failed = backend_results["failed"] + frontend_results["failed"] + cors_results["failed"]
    total_tests = backend_results["total"] + frontend_results["total"] + cors_results["total"]
    
    print(f"\n总测试数: {total_tests}")
    print(f"通过: {total_passed}")
    print(f"失败: {total_failed}")
    print(f"通过率: {(total_passed/total_tests*100):.1f}%")
    
    print("\n详细结果:")
    print(f"  后端 API 测试: {backend_results['passed']}/{backend_results['total']} 通过")
    print(f"  前端访问测试: {frontend_results['passed']}/{frontend_results['total']} 通过")
    print(f"  CORS 配置测试: {cors_results['passed']}/{cors_results['total']} 通过")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  前后端集成测试")
    print("=" * 60)
    print(f"\n后端地址: {BACKEND_URL}")
    print(f"前端地址: {FRONTEND_URL}")
    print("\n等待服务就绪（3秒）...")
    time.sleep(3)
    
    # 执行测试
    backend_results = test_backend_apis()
    frontend_results = test_frontend_access()
    cors_results = test_cors()
    
    # 打印总结
    print_summary(backend_results, frontend_results, cors_results)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

