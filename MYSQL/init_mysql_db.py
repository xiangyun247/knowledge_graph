#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL数据库初始化脚本
用于创建数据库表结构和导入初始数据
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.mysql_client import MySQLClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # 初始化MySQL客户端
        mysql_client = MySQLClient()
        
        # 连接数据库
        if not mysql_client.connect():
            logger.error("无法连接到MySQL数据库，请检查配置")
            return False
        
        # 获取SQL文件路径
        sql_file_path = os.path.join(Path(__file__).parent.parent, "init_mysql.sql")
        
        if not os.path.exists(sql_file_path):
            logger.error(f"SQL文件不存在: {sql_file_path}")
            return False
        
        logger.info(f"开始执行SQL文件: {sql_file_path}")
        
        # 执行SQL文件
        mysql_client.execute_sql_file(sql_file_path)
        
        logger.info("MySQL数据库初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 关闭数据库连接
        if 'mysql_client' in locals():
            mysql_client.disconnect()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)