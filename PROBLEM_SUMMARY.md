# 问题总结：Celery 任务未初始化错误

## 项目背景
- **目标**：使用 Hadoop MapReduce 实现批量处理 PDF 文件并构建知识图谱
- **技术栈**：
  - Hadoop 3.2.1 (Docker 容器)
  - FastAPI 后端
  - Celery (异步任务队列，当前已禁用)
  - Python 3

## 核心问题
即使已经完全移除了所有 Celery 相关的代码调用，系统仍然报错：
```
后台任务执行失败: Celery 任务未初始化
```

## 错误表现
1. **错误信息**：`Exception: Celery 任务未初始化`
2. **错误位置**：日志显示在 `backend/hadoop_api.py:220` 行
3. **错误时机**：在执行 Hadoop 处理任务时，在 `_run_hadoop_and_celery_in_background` 函数的 except 块中捕获

## 已尝试的解决方案

### 1. 代码层面
- ✅ 移除了 `hadoop_api.py` 中所有对 `get_celery_service()` 的导入和调用
- ✅ 重写了 `_run_hadoop_and_celery_in_background` 函数，完全移除了 Celery 相关逻辑
- ✅ 注释掉了 `get_batch_task_status` 中的 Celery 状态查询代码
- ✅ 修改了 `celery_service.py` 的 `get_celery_service()` 函数，确保初始化失败时不会抛出异常

### 2. 容器层面
- ✅ 多次重启后端容器 (`docker-compose restart backend`)
- ✅ 完全重建后端容器 (`docker-compose rm -f backend && docker-compose up -d backend`)
- ✅ 尝试清除 Python 缓存文件（`.pyc` 和 `__pycache__`）

### 3. 代码检查
- ✅ 确认 `hadoop_api.py` 中没有调用 `submit_chunk_processing_task` 的地方
- ✅ 确认 `hadoop_service.py` 中没有 Celery 相关代码
- ✅ 确认 `backend/app.py` 中没有在模块级别导入 Celery

## 当前代码状态

### `backend/hadoop_api.py` 中的 `_run_hadoop_and_celery_in_background` 函数
```python
def _run_hadoop_and_celery_in_background(task_id: str, file_ids: List[str], use_hadoop: bool) -> None:
    """
    在后台线程中执行 Hadoop 处理
    
    注意：当前版本仅执行 Hadoop 处理，不包含 Celery 任务
    """
    from backend.hadoop_service import get_hadoop_service  # 局部导入避免循环

    globals_ = _get_app_globals()
    tasks = globals_["tasks"]
    TaskStatus = globals_["TaskStatus"]

    try:
        # ... Hadoop 处理逻辑 ...
        hadoop_service = get_hadoop_service()
        hadoop_result = hadoop_service.process_files_with_hadoop(file_ids)
        # ... 处理结果 ...
    except Exception as e:
        # 第 220 行：这里捕获到异常，异常消息是 "Celery 任务未初始化"
        logger.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
        if task_id in tasks:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = f"后台任务执行失败: {e}"
            tasks[task_id]["progress"] = 100
```

### 关键发现
1. **异常来源不明**：代码中已经没有任何地方调用 Celery，但异常仍然被抛出
2. **异常类型**：`Exception: Celery 任务未初始化`（不是 `celery_service.py` 中的完整消息）
3. **异常位置**：在 `hadoop_service.process_files_with_hadoop()` 执行过程中抛出

## 可能的原因分析

### 1. Python 模块缓存问题
- `.pyc` 文件或 `__pycache__` 目录中可能还有旧代码
- 即使重建容器，如果代码是通过 volume 挂载的，缓存可能仍然存在

### 2. 间接导入问题
- `hadoop_service.py` 可能通过某个依赖链间接导入了 Celery
- `_get_app_globals()` 函数导入 `backend.app` 时，可能触发了某个模块的初始化

### 3. 异常传播问题
- 某个底层模块在初始化时尝试连接 Celery，失败后抛出异常
- 异常被上层代码捕获，但错误消息被修改或截断

### 4. 代码同步问题
- Docker volume 挂载的代码可能没有正确同步到容器内
- 容器内运行的代码版本可能与本地文件不一致

## 需要咨询的问题

1. **如何彻底清除 Python 模块缓存？**
   - 在 Docker 容器中，特别是通过 volume 挂载的代码
   - 如何确保 Python 重新加载所有模块？

2. **如何追踪异常的真正来源？**
   - 当异常在 except 块中被捕获时，如何找到最初抛出异常的位置？
   - 是否有工具可以追踪 Python 异常的完整调用栈？

3. **Docker volume 挂载的代码同步问题**
   - 如何确保容器内的代码与本地文件完全一致？
   - 是否有延迟或缓存导致代码不同步？

4. **Python 模块导入机制**
   - 如何检查某个模块是否被间接导入？
   - 如何防止某个模块在导入时执行初始化代码？

5. **异常处理最佳实践**
   - 如何在不影响主流程的情况下，优雅地处理可选依赖（如 Celery）的初始化失败？

## 相关文件位置

- `backend/hadoop_api.py` - 主要 API 路由和后台任务函数
- `backend/hadoop_service.py` - Hadoop 服务封装
- `backend/celery_service.py` - Celery 服务封装（已禁用但未删除）
- `backend/celery_app.py` - Celery 应用配置
- `backend/celery_tasks.py` - Celery 任务定义
- `docker-compose.yml` - Docker 服务配置

## 测试命令

```bash
# 运行测试脚本
python tests/test_batch_build.py

# 查看后端日志
docker logs kg-backend --tail 50

# 检查容器内代码
docker exec kg-backend cat /app/backend/hadoop_api.py | grep -A 10 "_run_hadoop_and_celery_in_background"
```

## 期望的解决方案

1. **短期目标**：让 Hadoop 处理流程能够正常运行，不因 Celery 相关错误而失败
2. **长期目标**：在需要时能够重新启用 Celery 集成，但当前阶段可以完全禁用

## 环境信息

- **操作系统**：Windows 10
- **Docker**：Docker Desktop for Windows
- **Python 版本**：3.x（容器内）
- **项目结构**：使用 Docker Compose 管理多个服务（Hadoop、Neo4j、MySQL、Redis、Backend）

