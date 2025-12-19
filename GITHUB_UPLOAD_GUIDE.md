# GitHub 上传指南

本指南将帮助你将项目上传到 GitHub。

## 📋 前置准备

### 1. 安装 Git

如果还没有安装 Git，请先下载安装：
- **Windows**: 访问 [https://git-scm.com/download/win](https://git-scm.com/download/win)
- 安装完成后，重启终端或 IDE

### 2. 配置 Git（首次使用）

```bash
# 设置用户名（替换为你的 GitHub 用户名）
git config --global user.name "你的GitHub用户名"

# 设置邮箱（替换为你的 GitHub 邮箱）
git config --global user.email "your-email@example.com"
```

### 3. 创建 GitHub 账号和仓库

1. 访问 [GitHub](https://github.com) 并登录（如果没有账号，先注册）
2. 点击右上角的 `+` 号，选择 `New repository`
3. 填写仓库信息：
   - **Repository name**: `knowledge_gragh`（或你喜欢的名字）
   - **Description**: `胰腺炎知识图谱RAG系统 - 基于Neo4j和RAG的医疗问答系统`
   - **Visibility**: 选择 `Public`（公开）或 `Private`（私有）
   - **不要**勾选 "Initialize this repository with a README"（因为本地已有代码）
4. 点击 `Create repository`

## 🚀 上传步骤

### 方法一：使用命令行（推荐）

#### 步骤 1: 打开终端

在项目根目录 `c:\Users\23035\PycharmProjects\knowledge_gragh` 打开终端（PowerShell 或 CMD）

#### 步骤 2: 初始化 Git 仓库

```bash
# 初始化 Git 仓库
git init

# 检查当前状态
git status
```

#### 步骤 3: 添加文件到暂存区

```bash
# 添加所有文件（.gitignore 中配置的文件会被自动忽略）
git add .

# 或者分步添加
git add *.py
git add *.md
git add requirements.txt
git add .gitignore
git add .env.example
# ... 等等
```

#### 步骤 4: 提交代码

```bash
# 提交代码（-m 后面是提交信息）
git commit -m "Initial commit: 胰腺炎知识图谱RAG系统"
```

#### 步骤 5: 连接到 GitHub 远程仓库

```bash
# 添加远程仓库（将 YOUR_USERNAME 和 YOUR_REPO_NAME 替换为你的实际信息）
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 例如：
# git remote add origin https://github.com/yourusername/knowledge_gragh.git
```

#### 步骤 6: 推送到 GitHub

```bash
# 推送到 GitHub（首次推送）
git push -u origin main

# 如果遇到分支名称问题，可能需要使用 master
git push -u origin master

# 或者先重命名分支
git branch -M main
git push -u origin main
```

### 方法二：使用 PyCharm（图形界面）

#### 步骤 1: 启用版本控制

1. 打开 PyCharm
2. 菜单栏：`VCS` → `Enable Version Control Integration`
3. 选择 `Git`，点击 `OK`

#### 步骤 2: 添加文件

1. 右键项目根目录 → `Git` → `Add`
2. 或者点击顶部工具栏的 `+` 号添加文件

#### 步骤 3: 提交代码

1. 点击顶部工具栏的 `✓`（Commit）按钮
2. 输入提交信息：`Initial commit: 胰腺炎知识图谱RAG系统`
3. 点击 `Commit`

#### 步骤 4: 推送到 GitHub

1. 菜单栏：`VCS` → `Git` → `Remotes...`
2. 点击 `+` 添加远程仓库：
   - Name: `origin`
   - URL: `https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git`
3. 点击 `OK`
4. 菜单栏：`VCS` → `Git` → `Push`
5. 选择 `origin` 和分支（main 或 master）
6. 点击 `Push`

## ⚠️ 重要注意事项

### 1. 确保敏感信息不被上传

以下文件**已经**在 `.gitignore` 中被忽略，不会上传：
- ✅ `.env` - 包含 API 密钥和密码
- ✅ `venv/` - Python 虚拟环境
- ✅ `logs/` - 日志文件
- ✅ `uploads/` - 上传的文件
- ✅ `__pycache__/` - Python 缓存文件
- ✅ `*.log` - 日志文件

### 2. 检查是否有敏感信息

在上传前，请确认：
- ✅ `.env` 文件没有被意外添加
- ✅ 代码中没有硬编码的密码或 API 密钥
- ✅ 所有敏感配置都使用环境变量

### 3. 创建 .env.example 文件

项目已包含 `.env.example` 文件，供其他开发者参考配置格式。

## 🔄 后续更新代码

### 使用命令行

```bash
# 查看修改状态
git status

# 添加修改的文件
git add .

# 提交修改
git commit -m "描述你的修改内容"

# 推送到 GitHub
git push
```

### 使用 PyCharm

1. 修改代码后，PyCharm 会在文件旁边显示颜色标记
2. 右键文件 → `Git` → `Add` 添加到暂存区
3. 点击 `✓`（Commit）提交
4. 点击 `↑`（Push）推送到 GitHub

## 📝 常见问题

### Q1: 提示 "fatal: not a git repository"

**解决方案**: 先执行 `git init` 初始化仓库

### Q2: 提示 "remote origin already exists"

**解决方案**: 
```bash
# 删除现有远程仓库
git remote remove origin

# 重新添加
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```

### Q3: 提示 "Authentication failed"

**解决方案**: 
- 使用 GitHub Personal Access Token 代替密码
- 访问 GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
- 生成新 token，复制后作为密码使用

### Q4: 想忽略已提交的文件

**解决方案**:
```bash
# 从 Git 中移除但保留本地文件
git rm --cached .env

# 提交更改
git commit -m "Remove .env from tracking"

# 推送到 GitHub
git push
```

### Q5: 分支名称冲突

**解决方案**:
```bash
# 重命名当前分支为 main
git branch -M main

# 推送到 GitHub
git push -u origin main
```

## 🎉 完成！

上传成功后，访问你的 GitHub 仓库页面，应该能看到所有代码文件。

## 📚 有用的 Git 命令参考

```bash
# 查看提交历史
git log

# 查看远程仓库
git remote -v

# 拉取最新代码
git pull

# 查看分支
git branch

# 创建新分支
git checkout -b feature/new-feature

# 切换分支
git checkout main
```

---

**提示**: 如果遇到任何问题，可以查看 Git 官方文档或 GitHub 帮助文档。

