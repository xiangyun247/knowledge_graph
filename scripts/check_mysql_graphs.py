#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 MySQL 中的知识图谱记录
"""

import sys
import os
import json
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 直接导入 MySQL 相关模块，避免导入 Neo4j
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import config

def check_mysql_graphs():
    """查询 MySQL 中的知识图谱记录"""
    try:
        # 创建 MySQL 连接
        try:
            import mysql.connector
            mysql_url = (
                f"mysql+mysqlconnector://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
                f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
                f"?charset=utf8mb4"
            )
        except ImportError:
            try:
                import pymysql
                mysql_url = (
                    f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
                    f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
                    f"?charset=utf8mb4"
                )
            except ImportError:
                raise ImportError("需要安装 mysql-connector-python 或 pymysql")
        
        engine = create_engine(mysql_url, echo=False)
        
        print("=" * 60)
        print("MySQL 知识图谱记录查询")
        print("=" * 60)
        
        # 查询所有图谱记录
        with engine.connect() as conn:
            query = text("""
            SELECT graph_id, graph_name, description, status, entity_count, relation_count, 
                   created_at, updated_at, graph_data, data_source, file_path
            FROM knowledge_graphs
            ORDER BY created_at DESC
            LIMIT 100
            """)
            
            result = conn.execute(query)
            graphs = []
            for row in result:
                graph = {
                    'graph_id': row[0],
                    'graph_name': row[1],
                    'description': row[2],
                    'status': row[3],
                    'entity_count': row[4] or 0,
                    'relation_count': row[5] or 0,
                    'created_at': str(row[6]) if row[6] else '',
                    'updated_at': str(row[7]) if row[7] else '',
                    'graph_data': row[8],
                    'data_source': row[9],
                    'file_path': row[10]
                }
                graphs.append(graph)
        
        if not graphs:
            print("\n[FAIL] 没有找到任何知识图谱记录")
            return
        
        print(f"\n[OK] 找到 {len(graphs)} 条知识图谱记录\n")
        
        for idx, graph in enumerate(graphs, 1):
            graph_id = graph.get('graph_id', '')
            graph_name = graph.get('graph_name', '')
            status = graph.get('status', '')
            entity_count = graph.get('entity_count', 0)
            relation_count = graph.get('relation_count', 0)
            created_at = graph.get('created_at', '')
            graph_data = graph.get('graph_data', {})
            
            print(f"【图谱 {idx}】")
            print(f"  ID: {graph_id}")
            print(f"  名称: {graph_name}")
            print(f"  状态: {status}")
            print(f"  实体数: {entity_count}")
            print(f"  关系数: {relation_count}")
            print(f"  创建时间: {created_at}")
            
            # 检查 graph_data 字段
            if graph_data:
                if isinstance(graph_data, str):
                    try:
                        graph_data = json.loads(graph_data)
                    except:
                        graph_data = {}
                
                nodes = graph_data.get('nodes', [])
                edges = graph_data.get('edges', graph_data.get('relations', []))
                
                print(f"  graph_data 状态: [OK] 存在")
                print(f"  节点数: {len(nodes)}")
                print(f"  边数: {len(edges)}")
                
                # 显示前几个节点的信息
                if nodes:
                    print(f"\n  前 3 个节点示例:")
                    for i, node in enumerate(nodes[:3], 1):
                        node_name = node.get('name', '未知')
                        node_category = node.get('category', node.get('type', '未知'))
                        print(f"    {i}. {node_name} (类型: {node_category})")
            else:
                print(f"  graph_data 状态: [FAIL] 不存在或为空")
            
            print()
        
        # 统计信息
        print("=" * 60)
        print("统计信息")
        print("=" * 60)
        
        total_entities = sum(g.get('entity_count', 0) for g in graphs)
        total_relations = sum(g.get('relation_count', 0) for g in graphs)
        completed = sum(1 for g in graphs if g.get('status') == 'completed')
        processing = sum(1 for g in graphs if g.get('status') == 'processing')
        failed = sum(1 for g in graphs if g.get('status') == 'failed')
        
        print(f"  总图谱数: {len(graphs)}")
        print(f"  已完成: {completed}")
        print(f"  处理中: {processing}")
        print(f"  失败: {failed}")
        print(f"  总实体数: {total_entities}")
        print(f"  总关系数: {total_relations}")
        
    except Exception as e:
        print(f"[FAIL] 查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_mysql_graphs()

