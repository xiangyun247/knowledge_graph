# MySQL root密码重置指南

## 问题分析
连接MySQL时出现以下错误：
```
ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)
```

这表明MySQL服务正在运行，但提供的root密码不正确。您需要重置MySQL的root密码。

## 重置步骤（Windows系统）

### 方法1：使用MySQL Installer重置密码

1. **打开MySQL Installer**
   - 在开始菜单中搜索"MySQL Installer"
   - 选择"MySQL Server"

2. **进入重新配置界面**
   - 点击"Reconfigure"按钮

3. **选择认证方式**
   - 选择"Authentication Method"
   - 选择"Use Legacy Authentication Method (Retain MySQL 5.x Compatibility)"或保持默认

4. **设置新密码**
   - 在"Accounts and Roles"步骤中
   - 为root用户设置新密码（例如：`password123`）
   - 确认密码

5. **完成配置**
   - 点击"Next"完成所有步骤
   - 重启MySQL服务

### 方法2：使用命令行重置密码

1. **停止MySQL服务**
   - 打开命令提示符（管理员权限）
   - 运行：`net stop mysql80` （根据您的MySQL版本，可能是mysql57或其他）

2. **以安全模式启动MySQL**
   - 运行：`mysqld --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.0\my.ini" --console --skip-grant-tables --shared-memory`
   - 保持此窗口打开

3. **打开新的命令提示符窗口**
   - 以管理员身份运行
   - 连接到MySQL：`mysql -u root`

4. **更新root密码**
   ```sql
   FLUSH PRIVILEGES;
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password_here';
   FLUSH PRIVILEGES;
   EXIT;
   ```

5. **重启MySQL服务**
   - 关闭安全模式窗口
   - 运行：`net start mysql80`

## 更新环境配置

1. **修改.env文件**
   - 编辑`C:\Users\23035\PycharmProjects\knowledge_gragh\.env`
   - 更新MySQL密码：
   ```ini
   MYSQL_PASSWORD=new_password_here
   ```

2. **测试连接**
   - 运行命令行测试：`mysql -u root -p -h localhost -P 3306`
   - 输入新密码，确认连接成功

3. **重新初始化数据库**
   ```bash
   python scripts/init_mysql_db.py
   ```

## 注意事项

1. **密码强度**：选择强密码，包含字母、数字和特殊字符
2. **记住密码**：确保记住或安全存储您的新密码
3. **服务名称**：根据您安装的MySQL版本，服务名称可能不同
4. **my.ini路径**：根据您的安装路径，my.ini文件位置可能不同

如果您仍然遇到问题，请检查：
- MySQL服务是否正在运行
- 防火墙设置是否允许MySQL连接
- 是否使用了正确的主机名和端口号

完成密码重置后，您应该能够成功连接到MySQL并初始化数据库。