#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析调试信息，找出问题根源

使用方法：
python scripts/analyze_debug_info.py debug_info_8fde1db9-a87a-4d1a-a110-98fbd56adf5e.json
"""

import json
import sys
import os

def analyze_debug_info(json_file):
    """分析调试信息"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    task = data.get("task", {})
    
    print("=" * 60)
    print("调试信息分析")
    print("=" * 60)
    
    # 1. 基本信息
    print(f"\n【任务状态】")
    print(f"  状态: {task.get('status')}")
    print(f"  进度: {task.get('progress')}%")
    print(f"  消息: {task.get('message')}")
    
    # 2. Hadoop 处理结果
    hadoop_result = task.get("hadoop_result", {})
    print(f"\n【Hadoop 处理结果】")
    print(f"  成功: {hadoop_result.get('success')}")
    if hadoop_result.get('success'):
        print(f"  最终输出: {hadoop_result.get('final_output')}")
        stages = hadoop_result.get('stages', {})
        print(f"  阶段:")
        for stage_name, stage_result in stages.items():
            print(f"    - {stage_name}: {'成功' if stage_result.get('success') else '失败'}")
    
    # 3. 调试信息检查
    print(f"\n【调试信息检查】")
    has_error_type = "error_type" in task
    has_error_message = "error_message" in task
    has_traceback = "traceback" in task
    has_debug = "debug" in task
    
    print(f"  error_type: {'YES' if has_error_type else 'NO'}")
    print(f"  error_message: {'YES' if has_error_message else 'NO'}")
    print(f"  traceback: {'YES' if has_traceback else 'NO'}")
    print(f"  debug: {'YES' if has_debug else 'NO'}")
    
    if not (has_error_type or has_error_message or has_traceback or has_debug):
        print("\n  [WARNING] 缺少所有调试信息字段！")
        print("  可能原因：")
        print("    1. 容器内代码版本不完整（缺少调试信息收集逻辑）")
        print("    2. 异常发生在设置调试信息之前")
        print("    3. 任务状态被其他地方覆盖")
    
    # 4. 兜底逻辑检查
    print(f"\n【兜底逻辑检查】")
    msg = task.get("message", "")
    hadoop_ok = hadoop_result.get("success", False)
    has_celery_error = "Celery" in msg and "未初始化" in msg
    
    print(f"  消息包含 'Celery 未初始化': {has_celery_error}")
    print(f"  Hadoop 处理成功: {hadoop_ok}")
    print(f"  应该触发兜底逻辑: {has_celery_error and hadoop_ok}")
    print(f"  实际任务状态: {task.get('status')}")
    
    if has_celery_error and hadoop_ok and task.get('status') == 'failed':
        print("\n  [WARNING] 兜底逻辑应该生效但没有生效！")
        print("  可能原因：")
        print("    1. 容器内代码版本不完整（缺少兜底逻辑）")
        print("    2. 任务状态在兜底逻辑之后被覆盖")
        print("    3. hadoop_result 在异常处理时还不存在")
    
    # 5. 关键发现
    print(f"\n【关键发现】")
    findings = []
    
    if hadoop_ok and task.get('status') == 'failed':
        findings.append("Hadoop 处理成功但任务被标记为失败")
    
    if not has_traceback:
        findings.append("缺少 traceback，无法定位异常来源")
    
    if not has_debug:
        findings.append("缺少 debug 信息，无法查看已加载的 Celery 模块")
    
    if has_celery_error and hadoop_ok and task.get('status') == 'failed':
        findings.append("兜底逻辑应该生效但没有生效")
    
    if findings:
        for i, finding in enumerate(findings, 1):
            print(f"  {i}. {finding}")
    else:
        print("  未发现明显问题")
    
    # 6. 建议
    print(f"\n【建议】")
    print("  1. 检查容器内代码版本是否完整")
    print("  2. 重新运行测试，获取新的调试信息")
    print("  3. 如果问题持续，检查是否有其他地方在修改任务状态")
    print("  4. 查看后端日志，确认异常发生的具体位置")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python scripts/analyze_debug_info.py <debug_info.json>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    if not os.path.exists(json_file):
        print(f"文件不存在: {json_file}")
        sys.exit(1)
    
    analyze_debug_info(json_file)

