# 调试指南：追踪 Celery 异常来源

## 概述

`backend/hadoop_api.py` 已经添加了完整的调试信息收集功能，可以帮助你快速定位 "Celery 任务未初始化" 异常的真实来源。

## 功能说明

### 1. 调试信息收集

当后台任务执行失败时，系统会自动收集以下信息并存储到任务状态中：

- **error_type**: 异常类型（如 `Exception`, `ValueError` 等）
- **error_message**: 异常消息
- **traceback**: 完整的 Python 调用栈（包含文件路径和行号）
- **debug.celery_modules_loaded**: 当时已加载的所有 Celery 相关模块及其文件路径

### 2. 兜底机制

如果 Hadoop 处理已成功完成，但后续仍触发 "Celery 未初始化" 错误，任务会被标记为 `COMPLETED`，消息为 "Hadoop 已完成（忽略非致命 Celery 错误）"，避免 Celery 错误影响 Hadoop 流程。

## 使用方法

### 步骤 1: 运行批处理测试

```bash
python tests/test_batch_build.py
```

记录返回的 `task_id`。

### 步骤 2: 查询任务状态

使用以下方式之一查询任务状态：

#### 方式 A: 使用 API 接口

```bash
curl http://127.0.0.1:5001/api/hadoop/status/{task_id}
```

#### 方式 B: 使用测试脚本

```bash
python scripts/test_debug_info.py
```

输入 `task_id`，脚本会自动显示所有调试信息。

### 步骤 3: 分析调试信息

查看返回的 JSON 中的以下字段：

```json
{
  "task": {
    "status": "failed",
    "error_type": "Exception",
    "error_message": "Celery 任务未初始化",
    "traceback": "Traceback (most recent call last):\n  File ...",
    "debug": {
      "python": "3.x.x",
      "celery_modules_loaded": [
        {
          "module": "backend.celery_service",
          "file": "/app/backend/celery_service.py"
        },
        {
          "module": "celery.app",
          "file": "/usr/local/lib/python3.x/site-packages/celery/app/__init__.py"
        }
      ]
    }
  }
}
```

### 关键信息解读

1. **traceback**: 
   - 查看最后一行，找到最初抛出异常的文件和行号
   - 检查调用栈，找出是哪个模块间接导入了 Celery

2. **celery_modules_loaded**:
   - 如果列表不为空，说明有模块被加载了
   - 检查每个模块的 `file` 路径，确认是否来自容器内的旧代码或镜像层

3. **error_message**:
   - 如果是 "Celery 任务未初始化"（短句），很可能是容器内旧代码
   - 如果是 "Celery 任务未初始化，已跳过知识图谱构建"（长句），来自 `celery_service.py`

## 验证容器代码版本

运行以下命令验证容器内的代码是否已更新：

```bash
docker exec kg-backend python -c "import backend.hadoop_api as m; import inspect; print('Module file:', m.__file__); print('Has debug function:', hasattr(m, '_collect_celery_debug_info')); src = inspect.getsource(m._run_hadoop_and_celery_in_background); print('Has debug collection:', '_collect_celery_debug_info' in src)"
```

预期输出：
```
Module file: /app/backend/hadoop_api.py
Has debug function: True
Has debug collection: True
```

## 常见问题排查

### 问题 1: 容器内代码版本不一致

**症状**: `traceback` 显示的文件路径或行号与本地代码不匹配

**解决方法**:
1. 检查 Docker volume 挂载是否正确
2. 重启容器: `docker-compose restart backend`
3. 清除 Python 缓存: `docker exec kg-backend find /app -name "*.pyc" -delete`

### 问题 2: 间接导入 Celery

**症状**: `celery_modules_loaded` 列表不为空，但代码中没有直接导入

**解决方法**:
1. 查看 `traceback` 找出导入路径
2. 检查 `celery_modules_loaded` 中每个模块的 `file` 路径
3. 使用 `python -X importtime` 追踪导入时间

### 问题 3: 异常来自旧代码

**症状**: `error_message` 是短句 "Celery 任务未初始化"，但本地代码中没有这个字符串

**解决方法**:
1. 检查容器内实际运行的代码: `docker exec kg-backend cat /app/backend/hadoop_api.py | grep -A 10 "Celery"`
2. 确认 volume 挂载路径正确
3. 重建容器: `docker-compose up -d --build backend`

## 下一步行动

根据调试信息的结果：

1. **如果 traceback 指向旧文件路径**: 检查 Docker volume 挂载
2. **如果 celery_modules_loaded 显示意外模块**: 追踪间接导入路径
3. **如果 Hadoop 成功但 Celery 失败**: 任务已标记为完成，可以继续使用 Hadoop 功能

## 相关文件

- `backend/hadoop_api.py`: 主 API 文件，包含调试信息收集逻辑
- `scripts/test_debug_info.py`: 测试脚本，用于查看调试信息
- `scripts/verify_container_code.py`: 验证脚本，检查容器代码版本
- `PROBLEM_SUMMARY.md`: 问题总结文档

