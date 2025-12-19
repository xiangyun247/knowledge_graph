# Git 安装详细指南（Windows）

## 📥 第一步：下载 Git

1. 访问 Git 官网：https://git-scm.com/download/win
2. 页面会自动检测你的系统，显示 "Download for Windows"
3. 点击下载按钮，会下载一个 `.exe` 安装文件（如：`Git-2.43.0-64-bit.exe`）

---

## 🔧 第二步：安装 Git

### 安装步骤详解

#### 步骤 1: 启动安装程序

双击下载的 `.exe` 文件，会看到欢迎界面。

**选择：**
- ✅ 直接点击 `Next`（下一步）

---

#### 步骤 2: 选择安装位置

**界面显示：** "Select Destination Location"

**说明：**
- 默认路径通常是：`C:\Program Files\Git`
- 可以保持默认，也可以选择其他位置

**选择：**
- ✅ 保持默认路径，点击 `Next`

---

#### 步骤 3: 选择组件（重要！）

**界面显示：** "Select Components"

**选项说明：**

- ✅ **Additional icons** - 额外图标
  - `On the Desktop` - 在桌面创建快捷方式（可选）
  
- ✅ **Windows Explorer integration** - Windows 资源管理器集成
  - `Git Bash Here` - 在右键菜单添加 "Git Bash Here"（**推荐勾选**）
  - `Git GUI Here` - 在右键菜单添加 "Git GUI Here"（可选）
  
- ✅ **Git LFS (Large File Support)** - Git 大文件支持（**推荐勾选**）
  
- ✅ **Associate .git* configuration files with the default text editor`** - 关联配置文件（可选）
  
- ✅ **Associate .sh files to be run with Bash`** - 关联 .sh 文件（可选）

**推荐选择：**
```
✅ Additional icons
   ✅ On the Desktop（可选）
✅ Windows Explorer integration
   ✅ Git Bash Here（推荐）
   ✅ Git GUI Here（可选）
✅ Git LFS (Large File Support)（推荐）
✅ Associate .git* configuration files with the default text editor（可选）
✅ Associate .sh files to be run with Bash（可选）
```

**选择：**
- ✅ 至少勾选 `Git Bash Here` 和 `Git LFS`
- 点击 `Next`

---

#### 步骤 4: 选择默认编辑器

**界面显示：** "Choosing the default editor used by Git"

**选项说明：**
- `Use the Nano editor by default` - 使用 Nano 编辑器（简单）
- `Use Vim (The ubiquitous text editor) as Git's default editor` - 使用 Vim（功能强大但复杂）
- `Use Notepad++ as Git's default editor` - 使用 Notepad++（如果已安装）
- `Use Visual Studio Code as Git's default editor` - 使用 VS Code（如果已安装）
- `Use Visual Studio as Git's default editor` - 使用 Visual Studio（如果已安装）

**推荐选择：**
- 如果你使用 **VS Code** 或 **PyCharm**，选择对应的选项
- 如果都不确定，选择 `Use Notepad++` 或 `Use the Nano editor by default`（最简单）

**选择：**
- ✅ 选择你熟悉的编辑器，或选择 `Nano`（最简单）
- 点击 `Next`

---

#### 步骤 5: 调整 PATH 环境（重要！）

**界面显示：** "Adjusting your PATH environment"

**选项说明：**

- `Use Git from Git Bash only` - 只在 Git Bash 中使用 Git
  - ❌ **不推荐**：只能在 Git Bash 中使用，PowerShell/CMD 无法使用
  
- `Git from the command line and also from 3rd-party software` - 从命令行和第三方软件使用 Git（**推荐**）
  - ✅ **推荐**：可以在 PowerShell、CMD、PyCharm 等任何地方使用 Git
  
- `Use Git and optional Unix tools from the Command Prompt` - 在命令提示符中使用 Git 和 Unix 工具
  - ⚠️ **谨慎**：会覆盖一些 Windows 命令

**推荐选择：**
- ✅ **选择第二个选项**：`Git from the command line and also from 3rd-party software`
- 这是最常用和最安全的选择

**选择：**
- ✅ 选择 `Git from the command line and also from 3rd-party software`
- 点击 `Next`

---

#### 步骤 6: 选择 HTTPS 传输后端

**界面显示：** "Choosing HTTPS transport backend"

**选项说明：**

- `Use the OpenSSL library` - 使用 OpenSSL 库（**推荐**）
  - ✅ 更稳定，兼容性更好
  
- `Use the native Windows Secure Channel library` - 使用 Windows 原生安全通道库
  - ⚠️ 某些企业网络可能需要这个

**推荐选择：**
- ✅ **选择第一个**：`Use the OpenSSL library`

**选择：**
- ✅ 选择 `Use the OpenSSL library`
- 点击 `Next`

---

#### 步骤 7: 配置行结束符（重要！）

**界面显示：** "Configuring the line ending conversions"

**选项说明：**

- `Checkout Windows-style, commit Unix-style line endings` - 检出 Windows 风格，提交 Unix 风格（**推荐**）
  - ✅ **推荐**：Windows 和 Linux/Mac 都能正常工作
  
- `Checkout as-is, commit Unix-style line endings` - 按原样检出，提交 Unix 风格
  - ⚠️ 可能导致 Windows 上文件显示异常
  
- `Checkout as-is, commit as-is` - 按原样检出和提交
  - ❌ **不推荐**：可能导致跨平台问题

**推荐选择：**
- ✅ **选择第一个**：`Checkout Windows-style, commit Unix-style line endings`

**选择：**
- ✅ 选择 `Checkout Windows-style, commit Unix-style line endings`
- 点击 `Next`

---

#### 步骤 8: 配置终端模拟器

**界面显示：** "Configuring the terminal emulator to use with Git Bash"

**选项说明：**

- `Use MinTTY (the default terminal of MSYS2)` - 使用 MinTTY（**推荐**）
  - ✅ **推荐**：更好的终端体验，支持复制粘贴
  
- `Use Windows' default console window` - 使用 Windows 默认控制台
  - ⚠️ 功能较少，但更轻量

**推荐选择：**
- ✅ **选择第一个**：`Use MinTTY (the default terminal of MSYS2)`

**选择：**
- ✅ 选择 `Use MinTTY (the default terminal of MSYS2)`
- 点击 `Next`

---

#### 步骤 9: 配置额外选项

**界面显示：** "Configuring extra options"

**选项说明：**

- `Default branch name` - 默认分支名称
  - `Let Git decide` - 让 Git 决定（旧版本可能是 master）
  - `Override the default branch name for new repositories` - 覆盖新仓库的默认分支名称
    - 可以输入 `main`（**推荐**）
  
- `Enable file system caching` - 启用文件系统缓存（**推荐勾选**）
  - ✅ 提高性能
  
- `Enable symbolic links` - 启用符号链接（可选）
  - ⚠️ 需要管理员权限

**推荐选择：**
```
✅ Default branch name
   ✅ Override the default branch name for new repositories
   输入：main
✅ Enable file system caching（推荐）
✅ Enable symbolic links（可选，如果需要）
```

**选择：**
- ✅ 设置默认分支为 `main`
- ✅ 勾选 `Enable file system caching`
- 点击 `Next`

---

#### 步骤 10: 配置实验性功能

**界面显示：** "Configuring experimental options"

**选项说明：**
- 通常是一些实验性功能，可以全部不选

**选择：**
- ✅ 保持默认（不勾选任何选项）
- 点击 `Install`（安装）

---

#### 步骤 11: 安装过程

等待安装完成，通常需要 1-2 分钟。

---

#### 步骤 12: 完成安装

**界面显示：** "Completing the Git Setup Wizard"

**选项说明：**
- `View Release Notes` - 查看发布说明（可选）
- `Launch Git Bash` - 启动 Git Bash（可选）

**选择：**
- ✅ 可以取消勾选这两个选项
- 点击 `Finish`

---

## ✅ 第三步：验证安装

### 方法 1: 使用 PowerShell 或 CMD

1. 打开 PowerShell 或 CMD
2. 输入以下命令：

```bash
git --version
```

如果显示版本号（如：`git version 2.43.0.windows.1`），说明安装成功！

### 方法 2: 使用 Git Bash

1. 在桌面或开始菜单找到 "Git Bash"
2. 打开后输入：

```bash
git --version
```

---

## 🔧 第四步：配置 Git（首次使用）

安装完成后，需要配置你的用户名和邮箱：

### 使用 PowerShell/CMD：

```bash
# 设置用户名（替换为你的 GitHub 用户名）
git config --global user.name "你的GitHub用户名"

# 设置邮箱（替换为你的 GitHub 邮箱）
git config --global user.email "your-email@example.com"

# 验证配置
git config --global --list
```

### 使用 Git Bash：

打开 Git Bash，执行相同的命令。

---

## 📋 快速参考：推荐配置总结

如果你想要最简单的配置，按照以下选择：

1. **组件选择：**
   - ✅ Git Bash Here
   - ✅ Git LFS

2. **默认编辑器：**
   - ✅ Nano（最简单）或你熟悉的编辑器

3. **PATH 环境：**
   - ✅ Git from the command line and also from 3rd-party software

4. **HTTPS 传输：**
   - ✅ Use the OpenSSL library

5. **行结束符：**
   - ✅ Checkout Windows-style, commit Unix-style line endings

6. **终端模拟器：**
   - ✅ Use MinTTY

7. **额外选项：**
   - ✅ 默认分支名称：`main`
   - ✅ Enable file system caching

---

## 🎉 完成！

安装完成后，你就可以使用 Git 了！

接下来可以：
1. 打开项目目录
2. 按照 `QUICK_START_GITHUB.md` 中的步骤上传代码到 GitHub

---

## ❓ 常见问题

### Q1: 安装后找不到 Git？

**解决方案：**
- 重启终端或 IDE（如 PyCharm）
- 如果还是不行，重启电脑

### Q2: 提示 "git is not recognized"？

**解决方案：**
- 检查安装时是否选择了 "Git from the command line and also from 3rd-party software"
- 重启终端或电脑

### Q3: 想修改配置怎么办？

**解决方案：**
- 重新运行安装程序，选择 "Modify"（修改）
- 或者使用命令行修改配置

---

**提示：** 如果安装过程中遇到任何问题，可以随时中断安装，重新运行安装程序。

