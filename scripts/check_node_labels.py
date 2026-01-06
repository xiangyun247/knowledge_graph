#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Neo4j 中节点的 labels
"""

import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from db.neo4j_client import Neo4jClient

def check_node_labels():
    """检查节点的 labels"""
    try:
        client = Neo4jClient()
        
        # 查询前 10 个节点及其 labels
        query = """
        MATCH (n)
        RETURN n, labels(n) as labels, id(n) as node_id
        LIMIT 10
        """
        
        results = client.execute_query(query)
        
        print("=" * 60)
        print("节点 Labels 检查")
        print("=" * 60)
        
        for idx, record in enumerate(results, 1):
            node = record['n']
            labels = record['labels']
            neo4j_id = record['node_id']
            
            node_props = dict(node)
            node_name = node_props.get('name', f'Node_{neo4j_id}')
            
            print(f"\n节点 {idx}:")
            print(f"  ID: {neo4j_id}")
            print(f"  名称: {node_name}")
            print(f"  Labels: {labels}")
            print(f"  Labels 数量: {len(labels)}")
            print(f"  Properties: {list(node_props.keys())}")
            if 'type' in node_props:
                print(f"  Properties.type: {node_props.get('type')}")
            if 'category' in node_props:
                print(f"  Properties.category: {node_props.get('category')}")
        
        # 统计所有节点的 labels
        stats_query = """
        MATCH (n)
        RETURN labels(n) as labels, count(*) as count
        ORDER BY count DESC
        LIMIT 20
        """
        
        stats_results = client.execute_query(stats_query)
        
        print("\n" + "=" * 60)
        print("Labels 统计")
        print("=" * 60)
        
        for record in stats_results:
            labels = record['labels']
            count = record['count']
            labels_str = labels[0] if labels else '无标签'
            print(f"  {labels_str}: {count} 个节点")
        
        client.close()
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_node_labels()













