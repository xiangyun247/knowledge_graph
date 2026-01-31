# MySQL 相关文件

本文件夹包含所有与 MySQL 数据库相关的文件。

## 文件说明

### SQL 脚本
- `init_mysql.sql` - MySQL 数据库初始化脚本，创建表结构
- `test_sql_import.sql` - SQL 导入测试脚本

### Python 脚本
- `init_mysql_db.py` - MySQL 数据库初始化 Python 脚本

### 文档
- `MYSQL_INTEGRATION.md` - MySQL 集成说明文档
- `MYSQL_PASSWORD_RESET.md` - MySQL 密码重置指南

## 使用说明

### 初始化数据库
```bash
# 使用 SQL 脚本
mysql -u root -p < init_mysql.sql

# 或使用 Python 脚本
python init_mysql_db.py
```

### 测试导入
```bash
mysql -u root -p < test_sql_import.sql
```





















