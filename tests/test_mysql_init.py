import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import uuid

# 加载环境变量
load_dotenv()

# 获取MySQL连接信息
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

# 创建数据库连接字符串 (使用pymysql驱动)
DATABASE_URL = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}'

print('=== MySQL数据库初始化测试 ===')
print(f'连接信息: {MYSQL_USER}@{MYSQL_HOST}:{MYSQL_PORT}')

# 创建引擎
engine = create_engine(DATABASE_URL)

# 连接并创建数据库
try:
    with engine.connect() as conn:
        conn.execution_options(isolation_level='AUTOCOMMIT')
        # 创建数据库
        conn.execute(text(f'CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE};'))
        print(f'✓ 数据库 {MYSQL_DATABASE} 创建成功')
        
        # 切换到创建的数据库
        conn.execute(text(f'USE {MYSQL_DATABASE};'))
        print(f'✓ 切换到数据库 {MYSQL_DATABASE}')
        
        # 创建知识图谱元数据表
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS knowledge_graphs (
            graph_id VARCHAR(36) PRIMARY KEY COMMENT '图谱唯一标识UUID',
            graph_name VARCHAR(255) NOT NULL COMMENT '图谱名称',
            description TEXT COMMENT '图谱描述',
            data_source VARCHAR(255) COMMENT '数据来源',
            file_path VARCHAR(255) COMMENT '原始文件路径',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '图谱状态',
            entity_count INT DEFAULT 0 COMMENT '实体数量',
            relation_count INT DEFAULT 0 COMMENT '关系数量',
            user_id VARCHAR(36) COMMENT '创建者ID',
            tags VARCHAR(255) COMMENT '标签，逗号分隔'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识图谱元数据';
        """))
        print('✓ 创建知识图谱元数据表成功')
        
        # 创建历史记录表
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS history_records (
            history_id VARCHAR(36) PRIMARY KEY COMMENT '历史记录唯一标识UUID',
            graph_id VARCHAR(36) NOT NULL COMMENT '关联的图谱ID',
            user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
            operation_type ENUM('create', 'update', 'query', 'delete') NOT NULL COMMENT '操作类型',
            operation_content TEXT COMMENT '操作内容',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            FOREIGN KEY (graph_id) REFERENCES knowledge_graphs(graph_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史操作记录';
        """))
        print('✓ 创建历史记录表成功')
        
        # 创建用户表
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(36) PRIMARY KEY COMMENT '用户唯一标识UUID',
            username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
            password VARCHAR(255) NOT NULL COMMENT '加密后的密码',
            email VARCHAR(100) UNIQUE COMMENT '邮箱',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息';
        """))
        print('✓ 创建用户表成功')
        
        # 创建索引
        conn.execute(text('CREATE INDEX idx_graphs_status ON knowledge_graphs(status);'))
        conn.execute(text('CREATE INDEX idx_graphs_created_at ON knowledge_graphs(created_at);'))
        conn.execute(text('CREATE INDEX idx_history_graph_id ON history_records(graph_id);'))
        conn.execute(text('CREATE INDEX idx_history_user_id ON history_records(user_id);'))
        conn.execute(text('CREATE INDEX idx_history_created_at ON history_records(created_at);'))
        print('✓ 创建索引成功')
        
        print('\n=== 数据库初始化完成！===')
        print('\n测试查询：')
        # 查询表结构
        result = conn.execute(text('SHOW TABLES;'))
        tables = result.fetchall()
        print('已创建的表:')
        for table in tables:
            print(f'  - {table[0]}')
            
except Exception as e:
    print(f'✗ 数据库操作失败: {e}')
    import traceback
    traceback.print_exc()
finally:
    engine.dispose()
    print('\n=== 连接已关闭 ===')
