# 脚本说明

本目录包含环境检查、诊断与手动测试脚本，与 `tests/` 下的自动化测试互补使用。

## 分类说明

### 环境与依赖检查（check_*）

| 脚本 | 说明 |
|------|------|
| `check_embedding_env.py` | 检查 Embedding 相关环境与依赖 |
| `check_hadoop_env.py` | 检查 Hadoop 环境与配置 |
| `check_hadoop_job_logs.py` | 查看 Hadoop 任务日志 |
| `check_mysql_graphs.py` | 检查 MySQL 中的图谱数据 |
| `check_node_labels.py` | 检查节点标签 |
| `check_agent_ready.py` | 检查 Agent 服务是否就绪 |
| `check_kb_chroma_ready.py` | 检查知识库 Chroma 是否就绪 |
| `check_frontend_backend_api.py` | **前后端 API 对接检查**：请求前端依赖的后端接口，确认 19 项通过后再做前端手工测试 |

### 运行与入口（run_*）

| 脚本 | 说明 |
|------|------|
| `run_backend_smoke.py` | 后端接口冒烟测试 |
| `run_agent_cli.py` | Agent 命令行交互 |

### 手动/集成测试（test_*）

| 脚本 | 说明 |
|------|------|
| `test_batch_build_with_sample_txt.py` | 使用 `data/examples/*.txt` 测试批量构建流程（无需真实 PDF） |
| `test_hadoop_build_with_real_file.py` | 使用真实文件测试 Hadoop 构建流程 |
| `test_kg_build_with_real_file.py` | 使用真实文件测试单文件知识图谱构建 |

### 初始化与维护

| 脚本 | 说明 |
|------|------|
| `init_database.py` | 数据库初始化 |
| `auto_clean_hadoop_configs.py` | 自动清理 Hadoop 相关配置 |
| `clean_container_configs.py` | 清理容器内配置 |
| `install_python_hadoop.sh` / `install_python_in_hadoop.sh` | Hadoop 环境中安装 Python 的脚本 |

## 使用建议

1. **联调前**：在项目根目录执行 `python scripts/check_frontend_backend_api.py`，确认前后端接口连通。
2. **手工测试批量构建**：先启动后端 `python run.py`，再执行 `python scripts/test_batch_build_with_sample_txt.py`。
3. **自动化测试**：使用 `pytest tests/` 运行 `tests/` 目录下的用例。
