#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件模块
用于存储应用程序的配置信息
"""

class Config:
    """配置类，包含应用程序的所有配置信息"""
    
    # MySQL数据库配置
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "123456"
    MYSQL_DATABASE = "knowledge_graph"
    
    # 文件上传配置
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".xlsx", ".xls"}
    
    # 知识图谱配置
    MAX_NODES = 1000
    MAX_RELATIONSHIPS = 2000
    
    # 历史记录配置
    MAX_HISTORY_RECORDS = 1000
    
    # API配置
    API_PREFIX = "/api"
    DEBUG = True
