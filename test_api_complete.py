"""
完整的 API 测试脚本
测试所有端点功能
"""
import requests
import json

BASE_URL = "http://localhost:5001"


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 70)
    print(f"🔍 {title}")
    print("=" * 70)


def test_health():
    """测试健康检查"""
    print_section("测试 0: 健康检查")

    response = requests.get(f"{BASE_URL}/health")
    print(f"✅ 状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"❌ 错误: {response.text}")


def test_stats():
    """测试统计信息"""
    print_section("测试 1: 获取统计信息")

    response = requests.get(f"{BASE_URL}/stats")
    print(f"✅ 状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"❌ 错误: {response.text}")


def test_search(entity_type, keyword):
    """测试搜索功能"""
    print_section(f"测试 2: 搜索 '{keyword}' ({entity_type})")

    params = {
        "entity_type": entity_type,
        "keyword": keyword,
        "limit": 10
    }

    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"✅ 状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"找到 {len(data)} 个结果:")
        for item in data[:5]:  # 只显示前5个
            print(f"  - {item.get('name', 'N/A')}")
    else:
        print(f"❌ 错误: {response.text}")


def test_query(question):
    """测试知识图谱查询"""
    print_section(f"测试 3: 查询 '{question}'")

    payload = {
        "question": question
    }

    # ✅ 修正：使用 /query 而不是 /rag/query
    response = requests.post(
        f"{BASE_URL}/query",  # ← 这里改了！
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"✅ 状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\n❓ 问题: {data.get('question', '')}")
        print(f"\n💡 答案:")
        print("-" * 70)
        print(data.get('answer', ''))
        print("-" * 70)

        # 如果有来源信息
        sources = data.get('sources', [])
        if sources:
            print(f"\n📚 参考来源: {len(sources)} 个")

    else:
        print(f"❌ 错误: {response.text}")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🚀" * 35)
    print("开始完整的 API 测试")
    print("🚀" * 35)

    results = []

    # 测试 0: 健康检查
    try:
        test_health()
        results.append(("健康检查", True))
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        results.append(("健康检查", False))

    # 测试 1: 统计信息
    try:
        test_stats()
        results.append(("统计信息", True))
    except Exception as e:
        print(f"❌ 统计信息测试失败: {e}")
        results.append(("统计信息", False))

    # 测试 2: 搜索功能
    search_tests = [
        ("Disease", "糖尿病"),
        ("Symptom", "头痛"),
        ("Drug", "阿司匹林"),
        ("Department", "内科")
    ]

    for entity_type, keyword in search_tests:
        try:
            test_search(entity_type, keyword)
            results.append((f"搜索-{keyword}", True))
        except Exception as e:
            print(f"❌ 搜索测试失败: {e}")
            results.append((f"搜索-{keyword}", False))

    # 测试 3: 知识图谱查询
    query_tests = [
        "高血压有什么症状？",
        "糖尿病怎么治疗？",
        "感冒应该看什么科？",
        "头痛是什么疾病的症状？"
    ]

    for i, question in enumerate(query_tests, 1):
        try:
            test_query(question)
            results.append((f"查询{i}", True))
        except Exception as e:
            print(f"❌ 查询测试失败: {e}")
            results.append((f"查询{i}", False))

    # 打印测试结果摘要
    print_section("📊 测试摘要")

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

    print("\n" + "=" * 70)
    print(f"总计: {passed_count}/{total_count} 测试通过 ({pass_rate:.1f}%)")

    if passed_count == total_count:
        print("\n🎉 所有测试通过！API 运行完美！")
    elif passed_count > 0:
        print(f"\n⚠️  有 {total_count - passed_count} 个测试失败，但部分功能正常")
    else:
        print("\n❌ 所有测试失败，请检查服务器是否正常运行")

    print("=" * 70)


if __name__ == "__main__":
    # 先检查服务器是否可访问
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ API 服务器正在运行")
            print(f"📍 服务器地址: {BASE_URL}")
            run_all_tests()
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务器")
        print("请确保服务器已启动: python api_server.py")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
