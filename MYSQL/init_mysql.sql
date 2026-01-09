-- MySQL数据库初始化脚本
-- 创建数据库
CREATE DATABASE IF NOT EXISTS knowledge_graph_system;
USE knowledge_graph_system;

-- 创建知识图谱元数据表
CREATE TABLE IF NOT EXISTS knowledge_graphs (
    graph_id VARCHAR(36) PRIMARY KEY COMMENT '图谱唯一标识UUID',
    graph_name VARCHAR(255) NOT NULL COMMENT '图谱名称',
    description TEXT COMMENT '图谱描述',
    data_source VARCHAR(255) COMMENT '数据来源',
    file_path VARCHAR(255) COMMENT '原始文件路径',
    graph_data JSON COMMENT '图谱数据（JSON格式，包含节点和关系）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '图谱状态',
    entity_count INT DEFAULT 0 COMMENT '实体数量',
    relation_count INT DEFAULT 0 COMMENT '关系数量',
    user_id VARCHAR(36) COMMENT '创建者ID',
    tags VARCHAR(255) COMMENT '标签，逗号分隔'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识图谱元数据';

-- 创建历史记录表
CREATE TABLE IF NOT EXISTS history_records (
    history_id VARCHAR(36) PRIMARY KEY COMMENT '历史记录唯一标识UUID',
    graph_id VARCHAR(36) NOT NULL COMMENT '关联的图谱ID',
    user_id VARCHAR(36) NOT NULL COMMENT '用户ID',
    operation_type ENUM('create', 'update', 'query', 'delete') NOT NULL COMMENT '操作类型',
    operation_content TEXT COMMENT '操作内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (graph_id) REFERENCES knowledge_graphs(graph_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史操作记录';

-- 创建用户表（可选，用于用户认证）
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(36) PRIMARY KEY COMMENT '用户唯一标识UUID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '加密后的密码',
    email VARCHAR(100) UNIQUE COMMENT '邮箱',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息';

-- 创建索引以提高查询性能
CREATE INDEX idx_graphs_status ON knowledge_graphs(status);
CREATE INDEX idx_graphs_created_at ON knowledge_graphs(created_at);
CREATE INDEX idx_history_graph_id ON history_records(graph_id);
CREATE INDEX idx_history_user_id ON history_records(user_id);
CREATE INDEX idx_history_created_at ON history_records(created_at);

-- 插入示例数据
INSERT INTO knowledge_graphs (graph_id, graph_name, description, data_source, status, entity_count, relation_count)
VALUES ('e7d1a8a0-1b9c-4d8e-8f9a-0b1c2d3e4f5a', '医学知识图谱示例', '包含疾病、症状、药物的医学知识图谱', 'sample_medical_data.json', 'completed', 1000, 2000);

INSERT INTO history_records (history_id, graph_id, user_id, operation_type, operation_content)
VALUES ('f8e2b9b1-2c0d-5e9f-90a1-1c2d3e4f5a6b', 'e7d1a8a0-1b9c-4d8e-8f9a-0b1c2d3e4f5a', 'user_001', 'create', '创建医学知识图谱示例'),
       ('g9f3c0c2-3d1e-6f0g-01a2-2c3d4e5f6a7c', 'e7d1a8a0-1b9c-4d8e-8f9a-0b1c2d3e4f5a', 'user_001', 'query', '查询高血压相关信息');