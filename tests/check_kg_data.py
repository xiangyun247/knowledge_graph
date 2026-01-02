"""
检查知识图谱数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from db.neo4j_client import Neo4jClient

def check_kg_data():
    """检查知识图谱数据"""
    print("=" * 60)
    print("检查知识图谱数据")
    print("=" * 60)
    
    try:
        client = Neo4jClient()
        
        # 检查连接
        if not client.verify_connection():
            print("[ERROR] Neo4j 连接失败")
            return
        
        print("\n[1] 获取统计信息...")
        stats = client.get_statistics()
        print(f"   节点总数: {stats.get('node_count', 0)}")
        print(f"   关系总数: {stats.get('relation_count', 0)}")
        print(f"   标签数: {stats.get('label_count', 0)}")
        print(f"   关系类型数: {stats.get('relation_type_count', 0)}")
        
        # 检查是否有疾病节点
        print("\n[2] 检查疾病节点...")
        query = "MATCH (d:Disease) RETURN count(d) as count"
        result = client.execute_query(query)
        disease_count = result[0]['count'] if result else 0
        print(f"   疾病节点数: {disease_count}")
        
        # 检查是否有"胰腺炎"相关的节点
        print("\n[3] 搜索'胰腺炎'相关节点...")
        query = """
        MATCH (n)
        WHERE n.name CONTAINS '胰腺炎' OR n.name CONTAINS '胰腺'
        RETURN labels(n) as labels, n.name as name, id(n) as id
        LIMIT 10
        """
        result = client.execute_query(query)
        if result:
            print(f"   找到 {len(result)} 个相关节点:")
            for item in result:
                print(f"     - {item['labels']}: {item['name']}")
        else:
            print("   未找到'胰腺炎'相关节点")
        
        # 检查所有节点类型
        print("\n[4] 检查各类型节点数量...")
        query = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """
        result = client.execute_query(query)
        if result:
            print("   节点类型分布:")
            for item in result:
                print(f"     {item['label']}: {item['count']}")
        else:
            print("   未找到任何节点")
        
        # 检查关系类型
        print("\n[5] 检查关系类型...")
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        LIMIT 10
        """
        result = client.execute_query(query)
        if result:
            print("   关系类型分布:")
            for item in result:
                print(f"     {item['type']}: {item['count']}")
        else:
            print("   未找到任何关系")
        
        client.close()
        
        print("\n" + "=" * 60)
        if stats.get('node_count', 0) == 0:
            print("[WARN] 知识图谱中没有数据！")
            print("建议：运行数据导入脚本导入测试数据")
        else:
            print("[OK] 知识图谱中有数据")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_kg_data()

