# 代码结构问题分析

## 🔍 发现的问题

### 1. **多个 FastAPI 应用入口（需要整合）**

当前有三个 FastAPI 应用入口：
- `api_server.py` - 提供 RAG 查询接口（/query, /search, /stats）
- `backend/app.py` - 提供文件上传、知识图谱构建等业务接口（/api/upload, /api/kg/build 等）
- `api/main.py` - 另一个 RAG 查询接口（与 api_server.py 功能类似）

**建议：**
- 保留 `backend/app.py` 作为主应用（因为它包含完整的业务功能）
- 将 `api_server.py` 和 `api/main.py` 的功能整合到 `backend/app.py` 中
- 或者明确分工：`backend/app.py` 处理业务逻辑，`api_server.py` 处理 RAG 查询

### 2. **重复的配置文件**

- `config.py` - 根目录，使用环境变量（.env 文件）
- `backend/config.py` - backend 目录，使用硬编码的 Config 类

**当前状态：**
- `backend/app.py` 使用 `db.mysql_client`，而 `db/mysql_client.py` 使用环境变量（不依赖 Config 类）
- `backend/mysql_client.py` 使用 `backend/config.py` 的 Config 类

**建议：**
- 统一使用根目录的 `config.py`（环境变量方式更灵活）
- 删除 `backend/config.py`，更新 `backend/mysql_client.py` 使用环境变量

### 3. **重复的 MySQL 客户端**

- `db/mysql_client.py` - 使用 SQLAlchemy，从环境变量读取配置
- `backend/mysql_client.py` - 使用 mysql.connector，从 Config 类读取配置

**当前状态：**
- `backend/app.py` 使用的是 `db.mysql_client.get_mysql_client()`
- `backend/mysql_client.py` 没有被使用

**建议：**
- 删除 `backend/mysql_client.py`（因为已经在使用 `db/mysql_client.py`）

### 4. **重复的导入脚本**

- `import_data.py` - 根目录，简单的示例脚本（使用 requests）
- `scripts/import_data.py` - scripts 目录，完整的 DataImporter 类
- `import_disease_data.py` - 根目录
- `scripts/import_medical_data.py` - scripts 目录

**建议：**
- 删除根目录的 `import_data.py` 和 `import_disease_data.py`
- 统一使用 `scripts/` 目录中的版本

### 5. **示例/临时文件（应删除）**

- `main.py` - PyCharm 生成的示例脚本，内容为空
- `package-lock.json` - Node.js 文件，不应该在 Python 项目中
- `upload_frontend.bat` - 临时批处理脚本
- `knowledge_gragh.code-workspace` - VS Code 工作区文件（可选删除）

### 6. **其他发现**

- `run.py` 中引用了已删除的 `app_combined.py`，需要更新

## 📋 整理建议优先级

### 高优先级（必须处理）
1. ✅ 删除示例文件：`main.py`
2. ✅ 删除 Node.js 文件：`package-lock.json`
3. ✅ 删除临时脚本：`upload_frontend.bat`
4. ✅ 删除重复的导入脚本：根目录的 `import_data.py` 和 `import_disease_data.py`

### 中优先级（建议处理）
5. ⚠️ 统一 FastAPI 应用入口：整合 `api_server.py` 和 `api/main.py` 到 `backend/app.py`
6. ⚠️ 删除未使用的 `backend/mysql_client.py`
7. ⚠️ 删除未使用的 `backend/config.py`（如果确认不使用）

### 低优先级（可选）
8. 删除 `knowledge_gragh.code-workspace`（如果不需要 VS Code 工作区配置）
9. 更新 `run.py` 中的引用（移除 `app_combined.py` 的检查）

## 🎯 推荐的项目结构

```
knowledge_gragh/
├── backend/            # 主应用（FastAPI）
│   └── app.py         # 统一的应用入口
├── api/               # API 路由模块（可选，如果拆分路由）
├── db/                # 数据库客户端
│   ├── mysql_client.py
│   └── neo4j_client.py
├── config.py          # 统一配置文件（环境变量）
├── scripts/           # 工具脚本
├── tests/             # 测试文件
├── MYSQL/             # MySQL 相关文件
├── docs/              # 文档
└── run.py             # 启动脚本





