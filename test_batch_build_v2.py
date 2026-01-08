#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试批量构建知识图谱流程（版本2）

该脚本用于测试完整的批量构建知识图谱流程，针对将PDF提取移到Hadoop之外的调整：
1. 生成测试文本和PDF文件
2. 上传文件到后端（此时会在上传阶段完成PDF提取）
3. 调用批量构建知识图谱接口（使用已提取的文本，跳过Hadoop PDF处理）
4. 检查任务状态
5. 验证知识图谱是否成功构建
"""

import os
import sys
import time
import requests
import uuid

# 设置后端API地址
BASE_URL = "http://localhost:5002"


def generate_test_files(num_files=2, output_dir="./test_files"):
    """
    生成测试文本和PDF文件
    
    Args:
        num_files: 生成的文件数量（每个类型）
        output_dir: 输出目录
    
    Returns:
        list: 生成的文件路径列表
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    file_paths = []
    
    # 生成文本文件
    for i in range(num_files):
        # 生成文本文件路径
        file_path = os.path.join(output_dir, f"test_text_{i+1}.txt")
        
        # 写入测试内容
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"这是测试文本文件 {i+1}\n")
            f.write("这是一个测试段落，用于测试知识图谱构建。\n")
            f.write("知识图谱是一种结构化的知识表示方法，可以用于存储和查询实体之间的关系。\n")
            f.write("实体是知识图谱中的基本单元，例如人物、组织、地点等。\n")
            f.write("关系是实体之间的连接，例如朋友关系、雇佣关系、地理位置关系等。\n")
        
        file_paths.append(file_path)
        print(f"生成测试文本文件: {file_path}")
    
    # 生成简单的PDF文件（使用文本内容模拟）
    for i in range(num_files):
        # 生成PDF文件路径
        pdf_path = os.path.join(output_dir, f"test_pdf_{i+1}.pdf")
        
        # 创建一个简单的PDF文件，只包含文本内容
        # 注意：这里我们不使用reportlab，而是直接创建一个包含PDF头的文本文件
        # 这种方法生成的PDF文件不是有效的PDF，但可以用于测试上传和提取流程
        with open(pdf_path, "wb") as f:
            # PDF文件头
            f.write(b"%PDF-1.4\n")
            f.write(b"1 0 obj\n")
            f.write(b"<< /Type /Catalog /Pages 2 0 R >>\n")
            f.write(b"endobj\n")
            f.write(b"2 0 obj\n")
            f.write(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n")
            f.write(b"endobj\n")
            f.write(b"3 0 obj\n")
            f.write(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\n")
            f.write(b"endobj\n")
            f.write(b"4 0 obj\n")
            f.write(b"<< /Length 50 >>\n")
            f.write(b"stream\n")
            f.write(b"BT /F1 12 Tf 100 700 Td (这是测试PDF文件 " + str(i+1).encode() + b") Tj ET\n")
            f.write(b"BT /F1 12 Tf 100 680 Td (这是PDF中的测试内容) Tj ET\n")
            f.write(b"endstream\n")
            f.write(b"endobj\n")
            f.write(b"5 0 obj\n")
            f.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n")
            f.write(b"endobj\n")
            f.write(b"xref\n")
            f.write(b"0 6\n")
            f.write(b"0000000000 65535 f \n")
            f.write(b"0000000010 00000 n \n")
            f.write(b"0000000053 00000 n \n")
            f.write(b"0000000102 00000 n \n")
            f.write(b"0000000166 00000 n \n")
            f.write(b"0000000256 00000 n \n")
            f.write(b"trailer\n")
            f.write(b"<< /Size 6 /Root 1 0 R >>\n")
            f.write(b"startxref\n")
            f.write(b"310\n")
            f.write(b"%%EOF\n")
        
        file_paths.append(pdf_path)
        print(f"生成测试PDF文件: {pdf_path}")
    
    return file_paths


def upload_files(file_paths):
    """
    上传文件到后端
    
    Args:
        file_paths: 文件路径列表
    
    Returns:
        list: 上传成功的文件ID列表
    """
    url = f"{BASE_URL}/api/hadoop/upload/batch"
    
    # 准备文件数据
    files = []
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        
        # 根据文件扩展名设置content-type
        if filename.endswith(".txt"):
            content_type = "text/plain"
        elif filename.endswith(".pdf"):
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"
        
        with open(file_path, "rb") as f:
            files.append(("files", (filename, f, content_type)))
    
    # 发送请求
    print(f"\n上传 {len(file_paths)} 个文件到 {url}")
    response = requests.post(url, files=files)
    
    # 检查响应
    if response.status_code != 2