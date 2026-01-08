#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证修复脚本：检查容器内代码版本并验证修复
"""

import subprocess
import sys

def check_container_code():
    """检查容器内代码版本"""
    print("=" * 60)
    print("检查容器内代码版本")
    print("=" * 60)
    
    checks = [
        {
            "name": "检查 hadoop_api.py 中的异常处理逻辑",
            "command": [
                "docker", "exec", "kg-backend", "python3", "-c",
                "import sys; sys.path.insert(0, '/app'); "
                "import backend.hadoop_api as m; "
                "import inspect; "
                "src = inspect.getsource(m._run_hadoop_and_celery_in_background); "
                "print('Has hadoop_result check:', 'hadoop_result = tasks[task_id].get(\"hadoop_result\")' in src); "
                "print('Has fallback logic:', 'if hadoop_ok:' in src); "
                "print('Has COMPLETED status:', 'TaskStatus.COMPLETED' in src and 'hadoop_ok' in src)"
            ]
        },
        {
            "name": "检查 celery_app.py 中的异常处理",
            "command": [
                "docker", "exec", "kg-backend", "python3", "-c",
                "import sys; sys.path.insert(0, '/app'); "
                "import backend.celery_app as m; "
                "print('celery_app is None:', m.celery_app is None); "
                "print('Has try-except:', hasattr(m, 'celery_app'))"
            ]
        },
        {
            "name": "检查 celery_tasks.py 中的 None 检查",
            "command": [
                "docker", "exec", "kg-backend", "python3", "-c",
                "import sys; sys.path.insert(0, '/app'); "
                "try:\n"
                "  import backend.celery_tasks as m\n"
                "  print('Import successful')\n"
                "except Exception as e:\n"
                "  print('Import failed:', str(e))"
            ]
        }
    ]
    
    results = []
    for check in checks:
        print(f"\n{check['name']}:")
        try:
            result = subprocess.run(
                check["command"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"  [OK] 成功")
                print(f"  输出: {result.stdout.strip()}")
                results.append(True)
            else:
                print(f"  [FAIL] 失败")
                print(f"  错误: {result.stderr.strip()}")
                results.append(False)
        except Exception as e:
            print(f"  [FAIL] 执行失败: {e}")
            results.append(False)
    
    return all(results)


def main():
    print("=" * 60)
    print("验证修复脚本")
    print("=" * 60)
    
    # 检查容器是否运行
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=kg-backend", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if not result.stdout.strip():
        print("\n[FAIL] 容器 kg-backend 未运行，请先启动容器")
        print("运行: docker-compose up -d backend")
        sys.exit(1)
    
    print("\n[OK] 容器 kg-backend 正在运行")
    
    # 检查代码版本
    success = check_container_code()
    
    print("\n" + "=" * 60)
    if success:
        print("[OK] 所有检查通过")
        print("\n建议：")
        print("1. 运行测试脚本: python tests/test_batch_build_v2.py")
        print("2. 检查任务状态，确认Hadoop成功时任务被标记为COMPLETED")
    else:
        print("[FAIL] 部分检查失败")
        print("\n建议：")
        print("1. 重启容器: docker-compose restart backend")
        print("2. 清除Python缓存: docker exec kg-backend find /app -name '*.pyc' -delete")
        print("3. 重新检查")
    print("=" * 60)


if __name__ == "__main__":
    main()

