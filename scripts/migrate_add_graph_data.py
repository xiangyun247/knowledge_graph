#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 knowledge_graphs 表添加 graph_data 字段
"""

import os
import sys

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 直接导入 MySQL 相关模块，避免导入 Neo4j
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_add_graph_data():
    """执行迁移：添加 graph_data 字段"""
    try:
        logger.info("开始执行数据库迁移：添加 graph_data 字段...")
        
        # 创建 MySQL 连接（尝试使用 mysqlconnector，如果没有则使用 pymysql）
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
        
        with engine.connect() as conn:
            # 先检查字段是否存在
            check_query = text("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'knowledge_graphs'
              AND COLUMN_NAME = 'graph_data'
            """)
            
            result = conn.execute(check_query)
            row = result.fetchone()
            field_exists = row[0] > 0 if row else False
            
            if field_exists:
                logger.info("graph_data 字段已存在，跳过迁移")
                return True
            
            # 字段不存在，添加字段
            alter_query = text("""
            ALTER TABLE knowledge_graphs 
            ADD COLUMN graph_data JSON COMMENT '知识图谱数据（节点和关系）'
            """)
            
            conn.execute(alter_query)
            conn.commit()
            logger.info("[OK] 成功添加 graph_data 字段到 knowledge_graphs 表")
        
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] 数据库迁移失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：添加 graph_data 字段")
    print("=" * 60)
    
    success = migrate_add_graph_data()
    
    if success:
        print("\n[OK] 迁移完成！")
        sys.exit(0)
    else:
        print("\n[FAIL] 迁移失败！")
        sys.exit(1)

