# MySQL数据库集成方案

## 1. 概述
本方案实现了在知识图谱系统中引入MySQL数据库，用于存储多个知识图谱的元数据和历史记录，解决了Neo4j单一数据库难以管理多个图谱的问题。

## 2. 实现内容

### 2.1 数据库设计

#### 知识图谱元数据表 (`knowledge_graphs`)
| 字段名 | 类型 | 描述 |
|--------|------|------|
| graph_id | VARCHAR(36) | 图谱唯一标识UUID |
| graph_name | VARCHAR(255) | 图谱名称 |
| description | TEXT | 图谱描述 |
| data_source | VARCHAR(255) | 数据来源 |
| file_path | VARCHAR(255) | 原始文件路径 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| status | ENUM | 图谱状态：pending/processing/completed/failed |
| entity_count | INT | 实体数量 |
| relation_count | INT | 关系数量 |
| user_id | VARCHAR(36) | 创建者ID |
| tags | VARCHAR(255) | 标签，逗号分隔 |

#### 历史记录表 (`history_records`)
| 字段名 | 类型 | 描述 |
|--------|------|------|
| history_id | VARCHAR(36) | 历史记录唯一标识UUID |
| graph_id | VARCHAR(36) | 关联的图谱ID |
| user_id | VARCHAR(36) | 用户ID |
| operation_type | ENUM | 操作类型：create/update/query/delete |
| operation_content | TEXT | 操作内容 |
| created_at | TIMESTAMP | 创建时间 |

#### 用户表 (`users`)
| 字段名 | 类型 | 描述 |
|--------|------|------|
| user_id | VARCHAR(36) | 用户唯一标识UUID |
| username | VARCHAR(50) | 用户名 |
| password | VARCHAR(255) | 加密后的密码 |
| email | VARCHAR(100) | 邮箱 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.2 已创建的文件

1. **数据库初始化SQL文件**：`init_mysql.sql`
   - 包含创建数据库、表结构和示例数据的SQL语句

2. **MySQL客户端模块**：`db/mysql_client.py`
   - 提供MySQL数据库连接和操作的封装
   - 支持执行SQL文件
   - 提供图谱和历史记录的CRUD操作

3. **数据库初始化脚本**：`scripts/init_mysql_db.py`
   - 用于执行SQL文件并初始化数据库

4. **环境配置**：`.env`
   - 添加了MySQL数据库连接配置项

5. **依赖配置**：`requirements.txt`
   - 添加了MySQL相关依赖

## 3. 使用说明

### 3.1 安装MySQL服务器

#### Windows
1. 下载MySQL Community Server：https://dev.mysql.com/downloads/mysql/
2. 安装时选择"Developer Default"配置
3. 设置root用户密码（记住这个密码）
4. 安装完成后，确保MySQL服务正在运行

#### Linux (Ubuntu)
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

#### 配置MySQL
- 允许远程连接（可选）
- 创建数据库和用户

### 3.2 配置环境变量

编辑`.env`文件，修改MySQL连接配置：

```ini
# ========== MySQL 配置 ==========
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=knowledge_graph_system
```

### 3.3 安装依赖

```bash
pip install mysql-connector-python sqlalchemy
```

### 3.4 初始化数据库

运行初始化脚本：

```bash
python scripts/init_mysql_db.py
```

### 3.5 测试MySQL连接

在Python中测试连接：

```python
from db.mysql_client import get_mysql_client

# 获取MySQL客户端实例
mysql_client = get_mysql_client()

# 测试连接
if mysql_client.connect():
    print("MySQL连接成功")
    
    # 测试创建图谱
    graph_id = mysql_client.create_graph(
        graph_name="测试图谱",
        description="这是一个测试图谱",
        data_source="test.csv"
    )
    print(f"创建的图谱ID: {graph_id}")
    
    # 测试获取图谱列表
    graphs = mysql_client.get_graphs()
    print(f"图谱列表: {graphs}")
    
    # 关闭连接
    mysql_client.disconnect()
else:
    print("MySQL连接失败")
```

## 4. 代码集成

### 4.1 图谱管理API集成

在`backend/app.py`中集成MySQL功能：

```python
from db.mysql_client import get_mysql_client

# 创建图谱管理路由
@app.post("/api/graphs")
async def create_graph(
    graph_data: dict,
    user_id: str = Depends(get_current_user_id)
):
    mysql_client = get_mysql_client()
    
    # 创建图谱元数据记录
    graph_id = mysql_client.create_graph(
        graph_name=graph_data["name"],
        description=graph_data.get("description", ""),
        data_source=graph_data.get("data_source", ""),
        file_path=graph_data.get("file_path", ""),
        user_id=user_id
    )
    
    # 更新状态为处理中
    mysql_client.update_graph_status(graph_id, "processing")
    
    # 创建历史记录
    mysql_client.create_history(
        graph_id=graph_id,
        user_id=user_id,
        operation_type="create",
        operation_content=f"创建图谱: {graph_data['name']}"
    )
    
    # 启动知识图谱构建任务
    # ...
    
    return {"graph_id": graph_id, "status": "processing"}
```

### 4.2 知识图谱构建完成后更新状态

在知识图谱构建完成后，更新MySQL中的状态：

```python
def build_kg_background(file_path, file_id, user_id=None):
    try:
        # ... 知识图谱构建代码 ...
        
        # 获取实体和关系数量
        entity_count = kg_builder.get_entity_count()
        relation_count = kg_builder.get_relation_count()
        
        # 更新MySQL中的图谱状态
        mysql_client = get_mysql_client()
        mysql_client.update_graph_status(
            graph_id=file_id,  # 假设file_id就是graph_id
            status="completed",
            entity_count=entity_count,
            relation_count=relation_count
        )
        
        # 创建历史记录
        mysql_client.create_history(
            graph_id=file_id,
            user_id=user_id or "system",
            operation_type="update",
            operation_content="图谱构建完成"
        )
        
    except Exception as e:
        # 更新失败状态
        mysql_client = get_mysql_client()
        mysql_client.update_graph_status(
            graph_id=file_id,
            status="failed"
        )
        
        # 创建历史记录
        mysql_client.create_history(
            graph_id=file_id,
            user_id=user_id or "system",
            operation_type="error",
            operation_content=f"图谱构建失败: {str(e)}"
        )
        
        raise e
```

## 5. 功能特点

### 5.1 支持SQL文件导入

`MySQLClient`类提供了`execute_sql_file`方法，支持直接执行SQL文件：

```python
mysql_client = MySQLClient()
mysql_client.connect()
mysql_client.execute_sql_file("init_mysql.sql")
mysql_client.disconnect()
```

### 5.2 事务支持

所有更新操作都支持事务：

```python
try:
    mysql_client.execute_update("INSERT INTO ...", params)
    mysql_client.execute_update("UPDATE ...", params)
    # 事务提交
    mysql_client.connection.commit()
except Exception as e:
    # 事务回滚
    mysql_client.connection.rollback()
    raise e
```

### 5.3 单例模式

`get_mysql_client()`函数提供了单例模式，确保全局只有一个MySQL连接实例：

```python
mysql_client1 = get_mysql_client()
mysql_client2 = get_mysql_client()
print(mysql_client1 is mysql_client2)  # 输出: True
```

## 6. 注意事项

1. **MySQL服务器必须运行**：确保MySQL服务正在运行，否则无法连接
2. **密码安全**：不要在代码中硬编码MySQL密码，使用环境变量
3. **连接关闭**：使用完毕后记得关闭数据库连接
4. **错误处理**：所有数据库操作都需要适当的错误处理
5. **性能优化**：为频繁查询的字段添加索引

## 7. 扩展建议

1. **添加数据库连接池**：提高并发性能
2. **实现分页查询**：处理大量数据
3. **添加缓存**：减少数据库查询次数
4. **实现权限管理**：控制用户对图谱的访问权限
5. **添加日志记录**：记录所有数据库操作

## 8. 故障排除

### 8.1 连接失败

- 检查MySQL服务是否正在运行
- 检查连接参数是否正确
- 检查防火墙设置

### 8.2 SQL语法错误

- 检查SQL文件中的语法
- 确保使用的是MySQL兼容的SQL语法

### 8.3 权限问题

- 确保MySQL用户有足够的权限
- 检查数据库和表的权限设置

## 9. 总结

本方案成功实现了MySQL数据库的集成，支持：

1. 存储多个知识图谱的元数据
2. 管理历史操作记录
3. 支持SQL文件导入
4. 提供完整的API接口
5. 与现有系统无缝集成

通过引入MySQL数据库，系统可以更好地管理多个知识图谱，提供更好的用户体验和性能。