"""
诊断搜索问题
"""
from db.neo4j_client import Neo4jClient
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def diagnose():
    """诊断数据库"""
    print("=" * 70)
    print("🔍 诊断数据库...")
    print("=" * 70)

    client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        with client.driver.session() as session:
            # 1. 查看所有疾病节点
            print("\n📋 所有疾病节点:")
            print("-" * 70)
            result = session.run("MATCH (d:Disease) RETURN d.name as name LIMIT 10")
            for record in result:
                print(f"  - {record['name']}")

            # 2. 查看所有症状节点
            print("\n📋 所有症状节点:")
            print("-" * 70)
            result = session.run("MATCH (s:Symptom) RETURN s.name as name LIMIT 10")
            for record in result:
                print(f"  - {record['name']}")

            # 3. 测试原始 CONTAINS 查询
            print("\n🔍 测试 CONTAINS 查询 (区分大小写):")
            print("-" * 70)
            keyword = "胰腺炎"
            query = """
            MATCH (n:Disease)
            WHERE toLower(n.name) CONTAINS toLower($keyword)
            RETURN n.name as name
            """
            result = session.run(query, keyword=keyword)
            count = 0
            for record in result:
                print(f"  ✅ 找到: {record['name']}")
                count += 1
            if count == 0:
                print(f"  ❌ 未找到包含 '{keyword}' 的结果")

            # 4. 测试正则表达式查询
            print("\n🔍 测试正则表达式查询 (不区分大小写):")
            print("-" * 70)
            query = """
            MATCH (n:Disease)
            WHERE n.name =~ $regex
            RETURN n.name as name
            """
            regex = f"(?i).*{keyword}.*"
            result = session.run(query, regex=regex)
            count = 0
            for record in result:
                print(f"  ✅ 找到: {record['name']}")
                count += 1
            if count == 0:
                print(f"  ❌ 未找到包含 '{keyword}' 的结果")

            # 5. 测试精确匹配
            print("\n🔍 测试精确匹配:")
            print("-" * 70)
            query = "MATCH (n:Disease {name: $keyword}) RETURN n.name as name"
            result = session.run(query, keyword=keyword)
            count = 0
            for record in result:
                print(f"  ✅ 找到: {record['name']}")
                count += 1
            if count == 0:
                print(f"  ❌ 未找到 '{keyword}'")

    finally:
        client.close()


if __name__ == "__main__":
    diagnose()
