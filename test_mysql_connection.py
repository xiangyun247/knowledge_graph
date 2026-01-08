#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试MySQL连接脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from db.mysql_client import MySQLClient

# 从环境变量加载配置
from dotenv import load_dotenv
load_dotenv()

def test_mysql_connection():
    """测试MySQL连接"""
    print("测试MySQL连接...")
    
    # 创建MySQL客户端实例
    mysql_client = MySQLClient()
    
    # 打印连接信息
    print(f"连接信息:")
    print(f"  主机: {mysql_client.host}")
    print(f"  端口: {mysql_client.port}")
    print(f"  用户: {mysql_client.user}")
    print(f"  密码: {'*' * len(mysql_client.password)}")
    print(f"  数据库: {mysql_client.database}")
    
    # 尝试连接
    print("\n尝试连接MySQL...")
    success = mysql_client.connect()
    
    if success:
        print("✅ MySQL连接成功!")
        
        # 尝试执行一个简单的查询
        print("\n执行测试查询...")
        try:
            result = mysql_client.execute_query("SELECT 1 + 1 AS sum")
            print(f"查询结果: {result}")
            print("✅ 测试查询成功!")
        except Exception as e:
            print(f"❌ 测试查询失败: {e}")
        
        # 尝试创建一个测试表
        print("\n尝试创建测试表...")
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS test_kg (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            mysql_client.execute_update(create_table_sql)
            print("✅ 测试表创建成功!")
            
            # 尝试插入一条测试数据
            insert_sql = "INSERT INTO test_kg (name) VALUES ('test_data')"
            row_count = mysql_client.execute_update(insert_sql)
            print(f"✅ 插入测试数据成功，影响行数: {row_count}")
            
            # 尝试查询测试数据
            select_sql = "SELECT * FROM test_kg"
            test_data = mysql_client.execute_query(select_sql)
            print(f"✅ 查询测试数据成功: {test_data}")
            
            # 尝试删除测试表
            drop_table_sql = "DROP TABLE test_kg"
            mysql_client.execute_update(drop_table_sql)
            print(f"✅ 删除测试表成功")
        except Exception as e:
            print(f"❌ 测试表操作失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ MySQL连接失败!")
    
    # 关闭连接
    mysql_client.disconnect()
    print("\n已关闭MySQL连接")

if __name__ == "__main__":
    test_mysql_connection()
