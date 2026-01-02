# 测试文件

本文件夹包含所有测试相关的文件。

## 测试文件说明

### 单元测试
- `test_kg_builder.py` - 知识图谱构建器测试
- `test_neo4j_client.py` - Neo4j 客户端测试
- `test_rag_pipeline.py` - RAG 流水线测试
- `test_embedding.py` - Embedding 模型测试
- `test_embedding_simple.py` - Embedding 模型简单测试

### 集成测试
- `test_api.py` - API 接口测试
- `test_api_complete.py` - API 完整测试
- `test_app.py` - 应用测试
- `test_backend_complete.py` - 完整后端功能测试
- `test_integration.py` - 前后端集成测试
- `test_query_api.py` - 智能问答接口测试
- `test_mysql_init.py` - MySQL 初始化测试
- `test_system.py` - 系统级测试
- `test_end_to_end.py` - 端到端集成测试

### 功能测试
- `test_data_persistence.py` - 数据持久化测试（MySQL graph_data）
- `test_mysql_neo4j_sync.py` - MySQL 到 Neo4j 数据同步测试
- `test_graph_switch.py` - 图谱切换功能测试

### 诊断工具
- `check_table.py` - 数据库表检查工具
- `check_kg_data.py` - 知识图谱数据检查工具
- `diagnose_search.py` - 搜索功能诊断工具
- `quick_test.py` - 快速测试脚本（检查服务状态）

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_api.py
pytest tests/test_system.py

# 运行功能测试
python tests/test_data_persistence.py
python tests/test_mysql_neo4j_sync.py
python tests/test_graph_switch.py
python tests/test_end_to_end.py

# 运行诊断工具
python tests/check_table.py
python tests/check_kg_data.py
python tests/diagnose_search.py
python tests/quick_test.py
```

## 测试分类

### 核心功能测试
- **数据持久化**：`test_data_persistence.py` - 验证数据是否正确保存到 MySQL
- **数据同步**：`test_mysql_neo4j_sync.py` - 验证 MySQL 到 Neo4j 的数据同步
- **图谱切换**：`test_graph_switch.py` - 验证图谱切换功能
- **端到端测试**：`test_end_to_end.py` - 验证完整工作流程

### API 测试
- **基础 API**：`test_api.py` - 基础 API 接口测试
- **完整 API**：`test_api_complete.py` - 完整 API 功能测试
- **后端应用**：`test_app.py` - 后端应用测试
- **智能问答**：`test_query_api.py` - 智能问答接口测试

### 系统测试
- **系统级**：`test_system.py` - 系统级综合测试
- **集成测试**：`test_integration.py` - 前后端集成测试
- **后端完整**：`test_backend_complete.py` - 完整后端功能测试





