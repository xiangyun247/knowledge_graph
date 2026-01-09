#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试脚本 - 测试纯文本知识图谱生成和MySQL存储
"""

import os
import sys
import uuid
from datetime import datetime

# 添加项目根目录到Python路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_ROOT)

def test_kg_generation():
    """测试知识图谱生成功能"""
    print("=" * 60)
    print("开始测试纯文本知识图谱生成")
    print("=" * 60)
    
    # 1. 创建简单的医学文本
    test_text = """
急性胰腺炎（AP）是一种常见的急腹症，其发病率逐年升高。
AP的主要症状包括腹痛、恶心、呕吐和发热。
诊断AP通常需要结合临床表现、血清淀粉酶和脂肪酶水平升高以及影像学检查结果。
AP的治疗包括液体复苏、疼痛管理、营养支持和病因治疗。
AP的并发症包括胰腺假性囊肿、胰腺坏死、感染和器官衰竭。
    """
    print("测试文本:")
    print(test_text)
    print("=" * 60)
    
    # 2. 导入并初始化知识图谱构建器
    try:
        from kg.builder import KnowledgeGraphBuilder
        from db.neo4j_client import Neo4jClient
        from llm.client import LLMClient
        from db.mysql_client import MySQLClient
        
        print("初始化客户端...")
        
        # 创建客户端实例
        neo4j_client = Neo4jClient()
        llm_client = LLMClient()
        mysql_client = MySQLClient()
        
        # 连接MySQL
        mysql_client.connect()
        
        # 创建知识图谱构建器
        builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client
        )
        
        print("客户端初始化成功！")
        print("=" * 60)
        
        # 3. 处理文本，生成知识图谱
        print("开始处理文本...")
        result = builder.process_text(test_text)
        
        # 打印完整的处理结果，方便调试
        print(f"处理结果完整信息: {result}")
        
        entities = result.get("entities", [])
        relations = result.get("relations", [])
        
        print(f"处理完成！生成 {len(entities)} 个实体，{len(relations)} 个关系")
        print("=" * 60)
        
        # 4. 打印生成的实体和关系
        print("生成的实体:")
        for entity in entities[:5]:  # 只显示前5个
            print(f"  - {entity['name']} ({entity['type']})")
        
        print("\n生成的关系:")
        for relation in relations[:5]:  # 只显示前5个
            print(f"  - {relation['subject']} {relation['predicate']} {relation['object']}")
        
        print("=" * 60)
        
        # 5. 将结果存储到MySQL
        print("开始存储到MySQL...")
        
        # 创建知识图谱记录
        graph_id = mysql_client.create_graph(
            graph_name=f"TestGraph_{uuid.uuid4().hex[:8]}",
            description="测试知识图谱",
            data_source="test_text",
            user_id="test_user"
        )
        print(f"创建的图谱ID: {graph_id}")
        
        # 更新图谱数据
        graph_data = {
            "nodes": entities,
            "relations": relations
        }
        mysql_client.update_graph_data(graph_id, graph_data)
        print("图谱数据已更新到MySQL")
        
        # 更新图谱状态和统计信息
        mysql_client.update_graph_status(
            graph_id=graph_id,
            status="completed",
            entity_count=len(entities),
            relation_count=len(relations)
        )
        print("图谱状态已更新")
        
        print("=" * 60)
        
        # 6. 从MySQL查询数据，验证存储效果
        print("从MySQL查询数据...")
        graph = mysql_client.get_graph_by_id(graph_id)
        if graph:
            print(f"查询到图谱: {graph['graph_name']}")
            print(f"实体数量: {graph['entity_count']}")
            print(f"关系数量: {graph['relation_count']}")
            print(f"状态: {graph['status']}")
        else:
            print("未查询到图谱")
        
        print("=" * 60)
        print("测试完成！")
        print(f"共生成 {len(entities)} 个实体，{len(relations)} 个关系")
        print(f"实体和关系已成功存储到MySQL")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 关闭客户端连接
        if 'neo4j_client' in locals():
            neo4j_client.close()
        if 'llm_client' in locals():
            llm_client.close()
        if 'mysql_client' in locals():
            mysql_client.disconnect()

if __name__ == "__main__":
    test_kg_generation()