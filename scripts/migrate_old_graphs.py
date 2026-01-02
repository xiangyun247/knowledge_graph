"""
迁移脚本：从 Neo4j 重新收集数据并保存到 MySQL

此脚本用于处理修复前上传的文件，这些文件的 graph_data 可能为空或包含合并数据。
脚本会：
1. 检查所有没有 graph_data 或 graph_data 为空的图谱
2. 从 Neo4j 收集所有数据（注意：Neo4j 中的数据可能是合并的）
3. 将数据保存到 MySQL 的 graph_data 字段

注意：
- 如果 Neo4j 中的数据是合并的（多个图谱的数据混在一起），
  此脚本会将所有数据保存到每个没有 graph_data 的图谱中。
- 这可能导致数据不准确，建议在迁移后重新上传文件以获得准确的数据。
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime, date

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    from db.mysql_client import MySQLClient
    from db.neo4j_client import Neo4jClient
    from loguru import logger
    import config
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def print_success(msg):
    """打印成功消息"""
    print(f"[OK] {msg}")

def print_error(msg):
    """打印错误消息"""
    print(f"[FAIL] {msg}")

def print_warning(msg):
    """打印警告消息"""
    print(f"[WARN] {msg}")

def print_info(msg):
    """打印信息消息"""
    print(f"[INFO] {msg}")

def clean_data(data):
    """递归清理数据中的 DateTime 对象"""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data(item) for item in data]
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif hasattr(data, '__dict__') and not isinstance(data, (str, int, float, bool, type(None))):
        # 处理 Neo4j 的特殊对象（如 DateTime）
        try:
            return str(data)
        except:
            return None
    else:
        return data

def get_graphs_without_data(mysql_client):
    """获取所有没有 graph_data 的图谱"""
    try:
        query = """
        SELECT graph_id, graph_name, data_source, status, entity_count, relation_count, created_at
        FROM knowledge_graphs
        WHERE graph_data IS NULL 
           OR graph_data = ''
           OR JSON_LENGTH(graph_data, '$.nodes') = 0
        ORDER BY created_at DESC
        """
        results = mysql_client.execute_query(query)
        
        graphs = []
        for row in results:
            graphs.append({
                'graph_id': row['graph_id'],
                'graph_name': row['graph_name'],
                'data_source': row['data_source'],
                'status': row['status'],
                'entity_count': row['entity_count'],
                'relation_count': row['relation_count'],
                'created_at': row['created_at']
            })
        
        return graphs
    except Exception as e:
        logger.error(f"获取图谱列表失败: {e}")
        return []

def migrate_graph_data(mysql_client, neo4j_client, graph_id, graph_name):
    """迁移单个图谱的数据"""
    try:
        print_info(f"正在迁移图谱: {graph_name} (ID: {graph_id})")
        
        # 从 Neo4j 收集所有数据
        neo4j_data = neo4j_client.get_all_nodes_and_relationships()
        all_nodes = neo4j_data.get('nodes', [])
        all_relationships = neo4j_data.get('relationships', [])
        
        print_info(f"  从 Neo4j 获取了 {len(all_nodes)} 个节点和 {len(all_relationships)} 个关系")
        
        if not all_nodes and not all_relationships:
            print_warning(f"  Neo4j 中没有数据，跳过此图谱")
            return False
        
        # 转换关系格式为 edges
        edges = []
        for rel in all_relationships:
            edge = {
                "id": rel.get("id", ""),
                "source": rel.get("source", ""),
                "target": rel.get("target", ""),
                "label": rel.get("label", rel.get("type", "")),
                "type": rel.get("type", rel.get("label", "")),
                "properties": rel.get("properties", {})
            }
            edges.append(edge)
        
        # 构建 graph_data
        graph_data = {
            "nodes": all_nodes,
            "edges": edges
        }
        
        # 清理数据
        cleaned_graph_data = clean_data(graph_data)
        
        # 保存到 MySQL
        mysql_client.update_graph_data(graph_id, cleaned_graph_data)
        
        print_success(f"  成功保存 {len(all_nodes)} 个节点和 {len(edges)} 个关系到 MySQL")
        return True
        
    except Exception as e:
        logger.error(f"迁移图谱 {graph_id} 失败: {e}")
        print_error(f"  迁移失败: {e}")
        return False

def main():
    """主函数"""
    print_header("图谱数据迁移脚本")
    
    print_info("正在初始化数据库连接...")
    
    # 初始化 MySQL 客户端
    mysql_client = MySQLClient()
    if not mysql_client.connect():
        print_error("无法连接到 MySQL 数据库")
        return False
    
    # 初始化 Neo4j 客户端（在 __init__ 中已建立连接）
    try:
        neo4j_client = Neo4jClient()
        if not neo4j_client.verify_connection():
            print_error("无法连接到 Neo4j 数据库")
            mysql_client.disconnect()
            return False
    except Exception as e:
        print_error(f"初始化 Neo4j 客户端失败: {e}")
        mysql_client.disconnect()
        return False
    
    try:
        # 获取所有没有 graph_data 的图谱
        print_info("正在检查需要迁移的图谱...")
        graphs_to_migrate = get_graphs_without_data(mysql_client)
        
        if not graphs_to_migrate:
            print_success("所有图谱都有 graph_data，无需迁移")
            return True
        
        print_info(f"找到 {len(graphs_to_migrate)} 个需要迁移的图谱")
        
        # 显示警告
        print_warning("\n重要提示：")
        print_warning("Neo4j 中的数据可能是合并的（多个图谱的数据混在一起）")
        print_warning("此脚本会将所有 Neo4j 数据保存到每个没有 graph_data 的图谱中")
        print_warning("这可能导致数据不准确，建议在迁移后重新上传文件以获得准确的数据\n")
        
        # 询问用户是否继续
        response = input("是否继续迁移？(y/n): ").strip().lower()
        if response != 'y':
            print_info("用户取消迁移")
            return False
        
        # 开始迁移
        print_header("开始迁移数据")
        
        success_count = 0
        fail_count = 0
        
        for i, graph in enumerate(graphs_to_migrate, 1):
            print(f"\n[{i}/{len(graphs_to_migrate)}] ", end="")
            
            if migrate_graph_data(
                mysql_client,
                neo4j_client,
                graph['graph_id'],
                graph['graph_name']
            ):
                success_count += 1
            else:
                fail_count += 1
        
        # 显示迁移结果
        print_header("迁移完成")
        print_success(f"成功迁移: {success_count} 个图谱")
        if fail_count > 0:
            print_error(f"迁移失败: {fail_count} 个图谱")
        
        return fail_count == 0
        
    except Exception as e:
        logger.error(f"迁移过程出错: {e}")
        print_error(f"迁移过程出错: {e}")
        return False
    finally:
        # 关闭连接
        mysql_client.disconnect()
        neo4j_client.close()
        print_info("数据库连接已关闭")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

