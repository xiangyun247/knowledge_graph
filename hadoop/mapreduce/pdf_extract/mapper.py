#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 文本提取 Mapper
用于 Hadoop MapReduce 任务

从 HDFS 读取 PDF 文件，提取文本内容
输出格式：文件路径 \t 文本内容
"""

import sys
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.error("pdfplumber 未安装，无法提取 PDF 文本")


def extract_pdf_text(file_path: str) -> str:
    """
    从 PDF 文件提取文本
    
    Args:
        file_path: PDF 文件路径
        
    Returns:
        提取的文本内容
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.error("pdfplumber 未安装")
        return ""
    
    try:
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            logger.info(f"处理 PDF 文件: {file_path}，共 {len(pdf.pages)} 页")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                # 清理文本
                page_text = page_text.replace("\u00a0", " ")
                text_parts.append(page_text)
        
        full_text = "\n\n".join(text_parts)
        logger.info(f"PDF 文本提取完成，总长度 {len(full_text)} 字符")
        return full_text
        
    except Exception as e:
        logger.error(f"提取 PDF 文本失败: {file_path}, 错误: {e}")
        return f"ERROR: {str(e)}"


def mapper():
    """
    Mapper 函数
    从标准输入读取文件路径，提取文本，输出到标准输出
    """
    try:
        # 从标准输入读取文件路径（每行一个文件路径）
        for line in sys.stdin:
            file_path = line.strip()
            
            if not file_path:
                continue
            
            logger.info(f"处理文件: {file_path}")
            
            # 提取 PDF 文本
            text = extract_pdf_text(file_path)
            
            # 输出：文件路径 \t 文本内容
            # 使用制表符分隔，便于 Reducer 处理
            output = f"{file_path}\t{text}"
            print(output)
            
    except Exception as e:
        logger.error(f"Mapper 执行出错: {e}")
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    mapper()


