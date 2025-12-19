# 🚀 快速上传到 GitHub

## 一键命令（复制粘贴执行）

```bash
# 1. 初始化 Git 仓库
git init

# 2. 添加所有文件
git add .

# 3. 提交代码
git commit -m "Initial commit: 胰腺炎知识图谱RAG系统"

# 4. 添加远程仓库（替换 YOUR_USERNAME 和 YOUR_REPO_NAME）
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 5. 推送到 GitHub
git branch -M main
git push -u origin main
```

## 📋 详细步骤说明

### 步骤 1: 在 GitHub 创建仓库

1. 访问 https://github.com/new
2. 填写仓库名称（如：`knowledge_gragh`）
3. 选择 Public 或 Private
4. **不要**勾选 "Initialize this repository with a README"
5. 点击 "Create repository"

### 步骤 2: 在项目目录执行命令

打开 PowerShell 或 CMD，进入项目目录：

```bash
cd c:\Users\23035\PycharmProjects\knowledge_gragh
```

然后执行上面的命令。

### 步骤 3: 如果遇到认证问题

GitHub 现在要求使用 Personal Access Token：

1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成后复制 token
5. 推送时，用户名输入你的 GitHub 用户名，密码输入刚才复制的 token

## ✅ 检查清单

上传前确认：
- [ ] `.env` 文件在 `.gitignore` 中（已配置）
- [ ] `venv/` 文件夹在 `.gitignore` 中（已配置）
- [ ] `logs/` 文件夹在 `.gitignore` 中（已配置）
- [ ] `uploads/` 文件夹在 `.gitignore` 中（已配置）
- [ ] 代码中没有硬编码的密码或 API 密钥

## 🎯 完成！

上传成功后，访问你的 GitHub 仓库即可看到代码。

