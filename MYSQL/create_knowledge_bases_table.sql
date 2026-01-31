-- 文档知识库列表表：持久化「我创建的」知识库名称，服务重启不丢失
-- 使用前请先 USE knowledge_graph_system; 或确保当前库正确

CREATE TABLE IF NOT EXISTS knowledge_bases (
    kb_id VARCHAR(64) PRIMARY KEY COMMENT '知识库唯一标识',
    name VARCHAR(128) NOT NULL COMMENT '知识库名称',
    user_id VARCHAR(64) NOT NULL COMMENT '创建者 user_id',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档知识库列表';

CREATE INDEX idx_knowledge_bases_user_id ON knowledge_bases(user_id);
