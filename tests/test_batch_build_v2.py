#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新的批量构建测试脚本 - 带详细调试信息

这个脚本会：
1. 生成测试PDF文件
2. 批量上传文件（PDF提取在上传阶段完成）
3. 触发批量构建（使用已提取的文本，跳过Hadoop PDF处理）
4. 轮询任务状态，并显示详细的调试信息
"""

import time
import json
import sys
import os
from pathlib import Path
import requests
import uuid

# ==== 配置 ====
# 容器内使用服务名称访问后端服务
BASE_URL = "http://backend:5001"  # 当前应用程序运行的端口
TEST_FILES_DIR = "./test_files"  # 测试文件存储目录
NUM_TEST_FILES = 2  # 每个类型的测试文件数量
# ==============


def get_real_pdf_files():
    """
    获取用户提供的真实PDF文件路径，支持在Docker容器内运行
    
    Returns:
        list: 真实PDF文件路径列表
    """
    print("=" * 60)
    print("步骤 1: 获取真实PDF文件")
    print("=" * 60)
    
    # 首先检查容器内是否有测试文件目录
    container_test_dir = "/app/test_files"
    test_files = []
    
    # 检查容器内的测试文件目录
    if os.path.exists(container_test_dir):
        print(f"[INFO] 发现容器内测试目录: {container_test_dir}")
        # 获取目录中的所有PDF文件
        for file in os.listdir(container_test_dir):
            if file.lower().endswith('.pdf'):
                file_path = os.path.join(container_test_dir, file)
                test_files.append(file_path)
                print(f"[INFO] 找到容器内PDF文件: {file_path}")
    
    # 如果没有找到PDF文件，生成一些简单的测试文本文件
    if not test_files:
        print("[INFO] 没有找到PDF文件，生成简单测试文本文件")
        
        # 创建测试文件目录
        os.makedirs(TEST_FILES_DIR, exist_ok=True)
        
        # 生成2个简单的测试文本文件
        for i in range(NUM_TEST_FILES):
            test_content = f"这是测试文本文件 {i+1}\n\n"
            test_content += "急性胰腺炎（AP）是一种常见的急腹症，其发病率逐年升高。\n"
            test_content += "AP的主要症状包括腹痛、恶心、呕吐和发热。\n"
            test_content += "诊断AP通常需要结合临床表现、血清淀粉酶和脂肪酶水平升高以及影像学检查结果。\n"
            
            file_path = os.path.join(TEST_FILES_DIR, f"test_{i+1}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            test_files.append(file_path)
            print(f"[INFO] 生成测试文件: {file_path}")
    
    if not test_files:
        raise RuntimeError("没有找到可用的测试文件")
    
    return test_files


def upload_batch_files(file_paths):
    """批量上传文件"""
    print("\n" + "=" * 60)
    print("步骤 2: 批量上传文件（PDF提取在上传阶段完成）")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/hadoop/upload/batch"
    
    files = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            print(f"[WARN] 文件不存在，跳过: {path}")
            continue
        
        # 根据文件扩展名设置content-type
        if path.suffix.lower() == ".txt":
            content_type = "text/plain"
        elif path.suffix.lower() == ".pdf":
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"
        
        files.append(
            (
                "files",
                (path.name, open(path, "rb"), content_type),
            )
        )
    
    if not files:
        raise RuntimeError("没有可用的测试文件")
    
    print(f"[INFO] 上传 {len(files)} 个文件到: {url}")
    resp = requests.post(url, files=files, timeout=600)
    print(f"[INFO] 上传响应状态码: {resp.status_code}")
    
    try:
        data = resp.json()
    except Exception:
        print("[ERROR] 无法解析 JSON 响应，原始内容：")
        print(resp.text)
        raise
    
    print("[INFO] 上传响应内容:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    
    if resp.status_code != 200:
        raise RuntimeError(f"批量上传失败: {data}")
    
    uploaded_file_ids = data.get("uploaded_file_ids") or []
    if not uploaded_file_ids:
        raise RuntimeError("上传成功但未返回 uploaded_file_ids")
    
    print(f"[INFO] 成功上传 {len(uploaded_file_ids)} 个文件")
    return uploaded_file_ids


def trigger_batch_build(file_ids):
    """触发批量构建"""
    print("\n" + "=" * 60)
    print("步骤 3: 触发批量构建（使用已提取的文本，跳过Hadoop PDF处理）")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/hadoop/build/batch"
    payload = {
        "file_ids": file_ids,
        "use_hadoop": True,
    }
    
    print(f"[INFO] 触发批量构建: {url}")
    print(f"[INFO] 请求 payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    resp = requests.post(url, json=payload, timeout=60)
    print(f"[INFO] 构建响应状态码: {resp.status_code}")
    
    try:
        data = resp.json()
    except Exception:
        print("[ERROR] 无法解析 JSON 响应，原始内容：")
        print(resp.text)
        raise
    
    print("[INFO] 构建响应内容:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"批量构建请求失败: {data}")
    
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError("响应中没有 task_id")
    
    return task_id


def poll_task_status(task_id, interval=5, max_minutes=30):
    """轮询任务状态，显示详细调试信息"""
    print("\n" + "=" * 60)
    print("步骤 4: 轮询任务状态（带详细调试信息）")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/hadoop/status/{task_id}"
    max_seconds = max_minutes * 60
    elapsed = 0
    poll_count = 0
    
    print(f"[INFO] 开始轮询任务状态, task_id={task_id}")
    print(f"[INFO] 轮询间隔: {interval} 秒, 最大等待时间: {max_minutes} 分钟")
    
    while True:
        poll_count += 1
        print(f"\n--- 第 {poll_count} 次轮询 (已等待 {elapsed} 秒) ---")
        
        try:
            resp = requests.get(url, timeout=30)
        except Exception as e:
            print(f"[ERROR] 请求失败: {e}")
            break
        
        try:
            data = resp.json()
        except Exception:
            print("[ERROR] 状态接口返回非 JSON：")
            print(resp.text)
            break
        
        task = data.get("task") or {}
        status = task.get("status")
        progress = task.get("progress")
        message = task.get("message")
        current_processing = task.get("current_processing")
        hadoop_result = task.get("hadoop_result", {})
        
        print(f"[STATUS] status={status}, progress={progress}%")
        print(f"[PROCESSING] {current_processing}")
        print(f"[MESSAGE] {message}")
        
        # 显示 Hadoop 结果
        if hadoop_result:
            hadoop_success = hadoop_result.get("success")
            print(f"[HADOOP] success={hadoop_success}")
            
            # 显示已提取的文本信息
            extracted_texts = hadoop_result.get("extracted_texts", {})
            if extracted_texts:
                print(f"[HADOOP] 已提取文本: {len(extracted_texts)} 个文件")
                for file_id, text in extracted_texts.items():
                    print(f"[HADOOP] 文件 {file_id}: {len(text)} 字符")
            
            if hadoop_success:
                final_output = hadoop_result.get("final_output")
                print(f"[HADOOP] final_output={final_output}")
        
        # 显示实体和关系创建情况
        if "entities_created" in task:
            print(f"[KG] 已创建实体: {task['entities_created']}")
        if "relations_created" in task:
            print(f"[KG] 已创建关系: {task['relations_created']}")
        
        # 显示调试信息（如果存在）
        if "error_type" in task:
            print(f"[DEBUG] error_type={task.get('error_type')}")
            print(f"[DEBUG] error_message={task.get('error_message')}")
            if "traceback" in task:
                print(f"[DEBUG] traceback (前500字符):")
                traceback_str = task.get("traceback", "")[:500]
                print(traceback_str)
        
        if "debug" in task:
            debug = task.get("debug", {})
            print(f"[DEBUG] debug信息: {json.dumps(debug, ensure_ascii=False, indent=2)}")
        
        # 检查任务是否完成
        if status in ("completed", "SUCCESS", "FAILED", "ERROR", "failed"):
            print("\n" + "=" * 60)
            print("任务结束，完整返回：")
            print("=" * 60)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            
            # 分析结果
            print("\n" + "=" * 60)
            print("结果分析：")
            print("=" * 60)
            if status in ("completed", "SUCCESS"):
                print("[OK] 任务成功完成")
                if hadoop_result.get("success"):
                    print("[OK] Hadoop 处理成功")
                else:
                    print("[FAIL] Hadoop 处理失败")
            else:
                print("[FAIL] 任务失败")
                if hadoop_result.get("success"):
                    print("[WARN] 警告: Hadoop 处理成功，但任务状态为失败")
                    print("[WARN] 这可能是因为 Celery 相关错误导致的")
                else:
                    print("[FAIL] Hadoop 处理失败")
            
            break
        
        time.sleep(interval)
        elapsed += interval
        if elapsed >= max_seconds:
            print("\n[WARN] 轮询超时，停止等待")
            print("=" * 60)
            print("最终状态：")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            break


def cleanup_test_files():
    """清理测试文件"""
    print("\n" + "=" * 60)
    print("步骤 5: 清理测试资源")
    print("=" * 60)
    print("[INFO] 由于使用了真实PDF文件，无需清理测试文件")


def main():
    print("=" * 60)
    print("批量构建测试脚本 v2 - 带详细调试信息")
    print("=" * 60)
    print("测试目标: 验证使用真实PDF文件构建知识图谱的流程是否正常工作")
    print("=" * 60)
    
    try:
        # 步骤 1: 获取真实PDF文件
        file_paths = get_real_pdf_files()
        print(f"\n[INFO] 找到 {len(file_paths)} 个真实PDF文件")
        
        # 步骤 2: 批量上传文件（PDF提取在上传阶段完成）
        file_ids = upload_batch_files(file_paths)
        print(f"\n[INFO] 上传得到 file_ids: {file_ids}")
        
        # 步骤 3: 触发批量构建（使用已提取的文本，跳过Hadoop PDF处理）
        task_id = trigger_batch_build(file_ids)
        print(f"\n[INFO] 收到 task_id: {task_id}")
        
        # 步骤 4: 轮询任务状态
        poll_task_status(task_id, interval=10, max_minutes=30)  # 增加超时时间到30分钟，适应较长的处理时间
        
        # 步骤 5: 清理测试资源
        cleanup_test_files()
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        return 0
    
    except Exception as e:
        print(f"\n[ERROR] 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        
        # 清理测试资源
        cleanup_test_files()
        
        print("\n" + "=" * 60)
        print("测试失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    main()

