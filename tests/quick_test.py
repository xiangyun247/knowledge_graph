"""
快速测试脚本 - 检查服务状态
"""
import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_backend():
    """测试后端服务"""
    print("=" * 60)
    print("测试后端服务")
    print("=" * 60)
    
    base_url = "http://localhost:5001"
    
    # 测试根路径
    print("\n[1] 测试根路径...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   [OK] 后端服务运行正常")
            return True
        else:
            print(f"   响应: {response.text[:100]}")
    except requests.exceptions.ConnectionError:
        print("   [FAIL] 无法连接到后端服务")
        print("   请确保后端服务已启动: python run.py")
        return False
    except Exception as e:
        print(f"   [ERROR] 错误: {e}")
        return False
    
    # 测试 API 文档
    print("\n[2] 测试 API 文档...")
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("   [OK] API 文档可访问: http://localhost:5001/docs")
        else:
            print(f"   [WARN] API 文档状态码: {response.status_code}")
    except Exception as e:
        print(f"   [ERROR] 错误: {e}")
    
    # 测试搜索接口
    print("\n[3] 测试实体搜索接口...")
    try:
        response = requests.get(f"{base_url}/api/search/entities?keyword=测试&limit=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] 搜索接口正常")
            print(f"   返回结果数: {len(data.get('data', []))}")
        else:
            print(f"   [WARN] 搜索接口状态码: {response.status_code}")
            print(f"   响应: {response.text[:100]}")
    except Exception as e:
        print(f"   [ERROR] 错误: {e}")
    
    # 测试图谱数据接口
    print("\n[4] 测试知识图谱数据接口...")
    try:
        response = requests.get(f"{base_url}/api/graph/data", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] 图谱数据接口正常")
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])
            print(f"   节点数: {len(nodes)}")
            print(f"   边数: {len(edges)}")
        else:
            print(f"   [WARN] 图谱数据接口状态码: {response.status_code}")
    except Exception as e:
        print(f"   [ERROR] 错误: {e}")

if __name__ == "__main__":
    print("\n等待后端服务启动（5秒）...")
    time.sleep(5)
    test_backend()
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

