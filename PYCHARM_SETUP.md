# PyCharm 配置 Embedding 模型指南

## 问题诊断

如果你在 PyCharm 中运行测试文件时遇到 `sentence-transformers 未安装` 的错误，这通常是因为 **PyCharm 使用的 Python 解释器与终端不同**。

## 解决方案

### 方法 1：在 PyCharm 中配置正确的 Python 解释器（推荐）

1. **打开 PyCharm 设置**
   - 点击 `File` -> `Settings`（或按 `Ctrl+Alt+S`）
   - 或者点击 `File` -> `Settings for New Projects...`

2. **选择 Python 解释器**
   - 在左侧菜单中找到 `Project: knowledge_gragh` -> `Python Interpreter`
   - 点击右上角的齿轮图标，选择 `Add Interpreter...` -> `Add Local Interpreter...`

3. **选择系统 Python**
   - 选择 `System Interpreter`
   - 在解释器路径中选择：`F:\Anaconda3\python.exe`（这是终端使用的 Python）
   - 点击 `OK`

4. **安装依赖**
   - 在 PyCharm 的 Terminal 中运行：
   ```bash
   pip install sentence-transformers
   ```
   - 或者使用 PyCharm 的包管理器：
     - 在 `Python Interpreter` 页面点击 `+` 号
     - 搜索 `sentence-transformers`
     - 点击 `Install Package`

### 方法 2：在 PyCharm Terminal 中安装依赖

1. **打开 PyCharm Terminal**
   - 点击底部的 `Terminal` 标签
   - 或者 `View` -> `Tool Windows` -> `Terminal`

2. **确认 Python 解释器**
   ```bash
   python --version
   python -c "import sys; print(sys.executable)"
   ```
   应该显示：`F:\Anaconda3\python.exe`

3. **安装依赖**
   ```bash
   pip install sentence-transformers
   ```

### 方法 3：使用虚拟环境（如果项目使用虚拟环境）

如果你使用的是虚拟环境：

1. **激活虚拟环境**
   ```bash
   # 在项目根目录
   .venv\Scripts\activate  # Windows
   # 或
   source venv/bin/activate  # Linux/Mac
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **在 PyCharm 中选择虚拟环境**
   - `File` -> `Settings` -> `Project: knowledge_gragh` -> `Python Interpreter`
   - 选择虚拟环境中的 Python 解释器

## 验证安装

运行诊断脚本：

```bash
python scripts/check_embedding_env.py
```

或者运行测试脚本：

```bash
python tests/test_embedding_simple.py
```

如果看到以下输出，说明安装成功：

```
[OK] sentence-transformers installed
Version: 5.2.0
[OK] Model loaded successfully!
Model dimension: 1024
```

## 常见问题

### Q1: PyCharm 显示 "sentence-transformers 未安装"，但终端中已安装

**原因**：PyCharm 使用的 Python 解释器与终端不同。

**解决**：按照上面的方法 1 配置正确的 Python 解释器。

### Q2: 模型下载很慢或失败

**原因**：网络连接问题或 HuggingFace 访问受限。

**解决**：
1. 检查网络连接
2. 使用 HuggingFace 镜像源（如果在中国）
3. 手动下载模型到本地缓存目录

### Q3: 内存不足

**原因**：模型加载需要约 2-3GB 内存。

**解决**：
1. 关闭其他程序释放内存
2. 使用更小的模型（如 `BAAI/bge-base-zh-v1.5`，768 维）

## 快速检查清单

- [ ] PyCharm 使用的 Python 解释器是 `F:\Anaconda3\python.exe`
- [ ] 在 PyCharm Terminal 中运行 `pip list | findstr sentence-transformers` 能看到包
- [ ] 运行 `python scripts/check_embedding_env.py` 所有检查都通过
- [ ] `.env` 文件中 `USE_LOCAL_EMBEDDING=True`

## 需要帮助？

如果以上方法都无法解决问题，请：

1. 运行诊断脚本并保存输出：
   ```bash
   python scripts/check_embedding_env.py > diagnosis.txt
   ```

2. 检查 PyCharm 的 Python 解释器设置截图

3. 提供错误信息的完整输出





