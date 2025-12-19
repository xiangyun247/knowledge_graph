#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL客户端模块
用于连接MySQL数据库，存储知识图谱和历史记录信息
"""

import os
import time
import uuid
from datetime import datetime, date
from typing import List, Dict, Optional, Any
import mysql.connector
from mysql.connector import Error
from config import Config
from loguru import logger


class MySQLClient:
    """
    MySQL客户端类，用于连接MySQL数据库并执行操作
    """
    
    def __init__(self):
        """初始化MySQL客户端"""
        self.config = Config()
        self.connection = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """连接到MySQL数据库"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE
            )
            
            if self.connection.is_connected():
                logger.info(f"成功连接到MySQL数据库: {self.config.MYSQL_DATABASE}")
                self.cursor = self.connection.cursor(dictionary=True)
        except Error as e:
            logger.error(f"MySQL连接失败: {e}")
            raise
    
    def create_tables(self):
        """创建必要的数据库表"""
        try:
            # 创建历史记录表
            history_table_query = """
            CREATE TABLE IF NOT EXISTS history_records (
                id VARCHAR(36) PRIMARY KEY,
                file_id VARCHAR(36),
                file_name VARCHAR(255),
                file_type VARCHAR(50),
                graph_id VARCHAR(36),
                task_id VARCHAR(36),
                entity_count INT DEFAULT 0,
                relationship_count INT DEFAULT 0,
                status ENUM('success', 'failed', 'processing') DEFAULT 'processing',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (graph_id) REFERENCES knowledge_graphs(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            
            # 创建知识图谱表
            knowledge_graph_table_query = """
            CREATE TABLE IF NOT EXISTS knowledge_graphs (
                id VARCHAR(36) PRIMARY KEY,
                file_id VARCHAR(36),
                file_name VARCHAR(255),
                graph_data JSON,
                entity_count INT DEFAULT 0,
                relationship_count INT DEFAULT 0,
                status ENUM('success', 'failed', 'processing') DEFAULT 'processing',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            
            self.cursor.execute(history_table_query)
            self.cursor.execute(knowledge_graph_table_query)
            self.connection.commit()
            logger.info("MySQL表创建成功")
        except Error as e:
            logger.error(f"创建MySQL表失败: {e}")
            self.connection.rollback()
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL连接已关闭")
    
    # ==================== 历史记录相关方法 ====================
    
    def create_history_record(self, file_id: str, file_name: str, file_type: str, task_id: str) -> str:
        """
        创建历史记录
        """
        try:
            history_id = str(uuid.uuid4())
            query = """
            INSERT INTO history_records (id, file_id, file_name, file_type, task_id)
            VALUES (%s, %s, %s, %s, %s)
            """
            values = (history_id, file_id, file_name, file_type, task_id)
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return history_id
        except Error as e:
            logger.error(f"创建历史记录失败: {e}")
            self.connection.rollback()
            raise
    
    def get_history_records(self) -> List[Dict[str, Any]]:
        """
        获取所有历史记录
        """
        try:
            query = "SELECT * FROM history_records ORDER BY created_at DESC"
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Error as e:
            logger.error(f"获取历史记录失败: {e}")
            raise
    
    def get_history_record(self, history_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取历史记录
        """
        try:
            query = "SELECT * FROM history_records WHERE id = %s"
            self.cursor.execute(query, (history_id,))
            return self.cursor.fetchone()
        except Error as e:
            logger.error(f"获取历史记录失败: {e}")
            raise
    
    def delete_history_record(self, history_id: str) -> bool:
        """
        删除历史记录
        """
        try:
            query = "DELETE FROM history_records WHERE id = %s"
            self.cursor.execute(query, (history_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            logger.error(f"删除历史记录失败: {e}")
            self.connection.rollback()
            raise
    
    def batch_delete_history_records(self, history_ids: List[str]) -> int:
        """
        批量删除历史记录
        """
        try:
            if not history_ids:
                return 0
            
            query = "DELETE FROM history_records WHERE id IN (%s)" % ','.join(['%s'] * len(history_ids))
            self.cursor.execute(query, history_ids)
            self.connection.commit()
            return self.cursor.rowcount
        except Error as e:
            logger.error(f"批量删除历史记录失败: {e}")
            self.connection.rollback()
            raise
    
    def clear_history_records(self) -> int:
        """
        清空所有历史记录
        """
        try:
            query = "DELETE FROM history_records"
            self.cursor.execute(query)
            self.connection.commit()
            return self.cursor.rowcount
        except Error as e:
            logger.error(f"清空历史记录失败: {e}")
            self.connection.rollback()
            raise
    
    def get_histories(self, graph_id=None, user_id=None, limit=100, offset=0):
        """
        获取历史记录
        """
        try:
            query = "SELECT * FROM history_records WHERE 1=1"
            params = []
            
            if graph_id:
                query += " AND graph_id = %s"
                params.append(graph_id)
            
            if user_id:
                query += " AND user_id = %s"
                params.append(user_id)
            
            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            
            # 添加调试信息，查看原始数据库记录
            import logging
            logging.info(f"原始历史记录数据: {records}")
            
            # 转换为前端期望的数据结构
            frontend_records = []
            for record in records:
                # 打印每条记录的详细信息
                logging.info(f"单条记录: {record}")
                
                # 1. 确定记录类型 - 更直接的判断方式
                record_type = 'chat'  # 默认聊天类型
                
                # 从record中提取关键字段
                file_type = record.get('file_type', '').lower()
                has_graph = record.get('graph_id') is not None
                has_entities = record.get('entity_count', 0) > 0
                file_name = record.get('file_name', '')
                
                # 根据多种条件判断记录类型
                if has_graph and has_entities:
                    record_type = 'graph'
                elif file_type in ['file', 'upload', 'document']:
                    record_type = 'upload'
                elif file_type == 'graph':
                    record_type = 'graph'
                
                logging.info(f"确定的record_type: {record_type}")
                
                # 2. 构建前端期望的content结构
                content = {}
                if record_type == 'chat':
                    content['question'] = file_name if file_name else '新对话'
                elif record_type == 'graph':
                    content['entity'] = file_name if file_name else '知识图谱'
                elif record_type == 'upload':
                    content['filename'] = file_name if file_name else '未知文件'
                
                logging.info(f"构建的content: {content}")
                
                # 3. 生成标题内容
                title_content = ''
                if record_type == 'chat':
                    title_content = content['question']
                elif record_type == 'graph':
                    title_content = content['entity']
                elif record_type == 'upload':
                    title_content = content['filename']
                
                # 4. 构建完整的历史记录对象
                frontend_record = {
                    'id': record.get('id', ''),
                    'type': record_type,
                    'title': title_content,
                    'content': content,
                    'status': record.get('status', 'completed'),
                    'entities': [],
                    'createTime': record.get('created_at', ''),
                    'updateTime': record.get('updated_at', record.get('created_at', ''))
                }
                
                logging.info(f"生成的前端记录: {frontend_record}")
                frontend_records.append(frontend_record)
            
            return frontend_records
        except Error as e:
            import logging
            logging.error(f"获取历史记录失败: {e}")
            return []
    
    def search_history_records(self, keyword: Optional[str] = None, 
                              type: Optional[str] = None, 
                              status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        搜索历史记录
        """
        try:
            query = "SELECT * FROM history_records WHERE 1=1"
            params = []
            
            if keyword:
                query += " AND (file_name LIKE %s OR file_id LIKE %s)"
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            if type:
                query += " AND file_type = %s"
                params.append(type)
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Error as e:
            logger.error(f"搜索历史记录失败: {e}")
            raise
    
    def get_history_stats(self) -> Dict[str, int]:
        """
        获取历史记录统计信息
        """
        try:
            # 获取总数
            self.cursor.execute("SELECT COUNT(*) as total FROM history_records")
            total = self.cursor.fetchone()['total']
            
            # 获取成功数量
            self.cursor.execute("SELECT COUNT(*) as success FROM history_records WHERE status = 'success'")
            success = self.cursor.fetchone()['success']
            
            # 获取失败数量
            self.cursor.execute("SELECT COUNT(*) as failed FROM history_records WHERE status = 'failed'")
            failed = self.cursor.fetchone()['failed']
            
            # 获取今日数量
            today = date.today().strftime("%Y-%m-%d")
            self.cursor.execute("SELECT COUNT(*) as today FROM history_records WHERE DATE(created_at) = %s", (today,))
            today_count = self.cursor.fetchone()['today']
            
            return {
                "total": total,
                "success": success,
                "failed": failed,
                "today": today_count
            }
        except Error as e:
            logger.error(f"获取历史记录统计失败: {e}")
            raise
    
    def save_history_record(self, data) -> str:
        """
        保存历史记录
        """
        try:
            history_id = str(uuid.uuid4())
            
            # 兼容前端数据结构
            file_id = data.get('file_id') or data.get('content', {}).get('fileId') or ''
            file_name = data.get('file_name') or data.get('content', {}).get('fileName') or ''
            file_type = data.get('file_type') or data.get('content', {}).get('fileType') or 'graph'
            graph_id = data.get('graph_id') or data.get('content', {}).get('graphId') or ''
            task_id = data.get('task_id') or data.get('content', {}).get('taskId') or history_id
            
            # 处理实体和关系数量
            entity_count = data.get('entity_count', 0)
            if entity_count == 0:
                # 从前端数据中获取实体数量
                entities = data.get('entities', [])
                entity_count = len(entities) if entities else 0
            
            relationship_count = data.get('relationship_count', 0)
            if relationship_count == 0:
                # 从前端数据中获取关系数量
                content = data.get('content', {})
                if isinstance(content, dict):
                    relationships = content.get('relationships', [])
                    relationship_count = len(relationships) if relationships else 0
            
            status = data.get('status', 'processing')
            
            query = """
            INSERT INTO history_records (id, file_id, file_name, file_type, graph_id, task_id, entity_count, relationship_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                history_id,
                file_id,
                file_name,
                file_type,
                graph_id,
                task_id,
                entity_count,
                relationship_count,
                status
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return history_id
        except Error as e:
            logger.error(f"保存历史记录失败: {e}")
            self.connection.rollback()
            raise
    
    def update_history_record_status(self, history_id: str, status: str) -> bool:
        """
        更新历史记录状态
        """
        try:
            query = "UPDATE history_records SET status = %s WHERE id = %s"
            self.cursor.execute(query, (status, history_id))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            logger.error(f"更新历史记录状态失败: {e}")
            self.connection.rollback()
            raise
    
    # ==================== 知识图谱相关方法 ====================
    
    def create_knowledge_graph_record(self, graph_id: str, file_id: str, file_name: str, 
                                     entity_count: int = 0, relationship_count: int = 0,
                                     status: str = "processing", task_id: str = None) -> str:
        """
        创建知识图谱记录
        """
        try:
            # 创建知识图谱
            kg_query = """
            INSERT INTO knowledge_graphs (id, file_id, file_name, entity_count, 
                                        relationship_count, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            kg_values = (graph_id, file_id, file_name, entity_count, relationship_count, status)
            
            self.cursor.execute(kg_query, kg_values)
            
            # 如果有任务ID，更新历史记录
            if task_id:
                self.update_history_record_task(task_id, graph_id, entity_count, relationship_count, status)
            
            self.connection.commit()
            return graph_id
        except Error as e:
            logger.error(f"创建知识图谱记录失败: {e}")
            self.connection.rollback()
            raise
    
    def update_knowledge_graph_record(self, graph_id: str, **kwargs) -> bool:
        """
        更新知识图谱记录
        """
        try:
            if not kwargs:
                return False
            
            set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
            values = list(kwargs.values()) + [graph_id]
            
            query = f"UPDATE knowledge_graphs SET {set_clause} WHERE id = %s"
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            logger.error(f"更新知识图谱记录失败: {e}")
            self.connection.rollback()
            raise
    
    def get_knowledge_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取知识图谱
        """
        try:
            query = "SELECT * FROM knowledge_graphs WHERE id = %s"
            self.cursor.execute(query, (graph_id,))
            return self.cursor.fetchone()
        except Error as e:
            logger.error(f"获取知识图谱失败: {e}")
            raise
    
    def get_knowledge_graph_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        根据文件ID获取知识图谱
        """
        try:
            query = "SELECT * FROM knowledge_graphs WHERE file_id = %s"
            self.cursor.execute(query, (file_id,))
            return self.cursor.fetchone()
        except Error as e:
            logger.error(f"根据文件ID获取知识图谱失败: {e}")
            raise
    
    def delete_knowledge_graph(self, graph_id: str) -> bool:
        """
        删除知识图谱
        """
        try:
            query = "DELETE FROM knowledge_graphs WHERE id = %s"
            self.cursor.execute(query, (graph_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            logger.error(f"删除知识图谱失败: {e}")
            self.connection.rollback()
            raise
    
    def update_history_record_task(self, task_id: str, graph_id: str, 
                                  entity_count: int = 0, relationship_count: int = 0,
                                  status: str = "processing") -> bool:
        """
        更新历史记录任务信息
        """
        try:
            query = """
            UPDATE history_records 
            SET graph_id = %s, entity_count = %s, relationship_count = %s, status = %s
            WHERE task_id = %s
            """
            values = (graph_id, entity_count, relationship_count, status, task_id)
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            logger.error(f"更新历史记录任务失败: {e}")
            self.connection.rollback()
            raise

# 创建全局MySQL客户端实例
_mysql_client_instance = None

def get_mysql_client():
    """
    获取MySQL客户端实例（单例模式）
    """
    global _mysql_client_instance
    if _mysql_client_instance is None:
        _mysql_client_instance = MySQLClient()
    return _mysql_client_instance

if __name__ == "__main__":
    # 测试MySQL客户端
    try:
        client = MySQLClient()
        logger.info("MySQL客户端测试成功")
    except Exception as e:
        logger.error(f"MySQL客户端测试失败: {e}")
        raise