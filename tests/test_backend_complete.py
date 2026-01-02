"""
完整后端功能测试
测试 backend/app.py 中的所有主要接口
"""
import sys
import requests
from pathlib import Path

BACKEND_URL = "http://localhost:5001"

def test_all_apis():
    """测试所有后端 API"""
    print("=" * 60)
    print("完整后端功能测试")
    print("=" * 60)
    
    results = {"passed": 0, "failed": 0, "total": 0}
    
    # 1. 实体搜索
    print("\n[1] 实体搜索接口")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/search/entities",
            params={"keyword": "胰腺炎", "limit": 10},
            timeout=5
        )
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 2. 图谱数据
    print("\n[2] 知识图谱数据接口")
    results["total"] += 1
    try:
        response = requests.get(f"{BACKEND_URL}/api/graph/data", timeout=5)
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 3. 历史记录列表
    print("\n[3] 历史记录列表接口")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/history/list",
            params={"page": 1, "page_size": 10},
            timeout=5
        )
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 4. 知识图谱列表
    print("\n[4] 知识图谱列表接口")
    results["total"] += 1
    try:
        response = requests.get(f"{BACKEND_URL}/api/kg/list", timeout=5)
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 5. 图谱实体搜索
    print("\n[5] 图谱实体搜索接口")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/graph/entities/search",
            params={"keyword": "疾病", "limit": 5},
            timeout=5
        )
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 6. 历史记录统计
    print("\n[6] 历史记录统计接口")
    results["total"] += 1
    try:
        response = requests.get(f"{BACKEND_URL}/api/history/stats", timeout=5)
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    # 7. 图谱关系搜索
    print("\n[7] 图谱关系搜索接口")
    results["total"] += 1
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/graph/relations/search",
            params={"keyword": "治疗", "limit": 5},
            timeout=5
        )
        if response.status_code == 200:
            print("   [OK] 测试通过")
            results["passed"] += 1
        else:
            print(f"   [FAIL] 状态码: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        results["failed"] += 1
    
    print("\n" + "=" * 60)
    print(f"测试完成: {results['passed']}/{results['total']} 通过")
    print(f"通过率: {(results['passed']/results['total']*100):.1f}%")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    test_all_apis()

