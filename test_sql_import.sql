-- 测试SQL导入功能的简单脚本
-- 创建一个测试表
CREATE TABLE IF NOT EXISTS test_table (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入测试数据
INSERT INTO test_table (name, description) VALUES
('测试数据1', '这是第一条测试数据'),
('测试数据2', '这是第二条测试数据'),
('测试数据3', '这是第三条测试数据');

-- 查询测试数据
SELECT * FROM test_table;