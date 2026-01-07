#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本分块 Mapper
用于 Hadoop MapReduce 任务

从 HDFS 读取清洗后的文本，进行分块处理
输出格式：文件路径_块编号 \t 文本块内容
"""

import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def split_into_chunks(text: str, chunk_size: int = 1000) -> list:
    """
    将文本分块
    
    Args:
        text: 输入文本
        chunk_size: 每个块的字符数（默认 1000）
        
    Returns:
        文本块列表
    """
    if not text:
        return []
    
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 是空格
        
        if current_length + word_length > chunk_size and current_chunk:
            # 当前块已满，保存并开始新块
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    # 添加最后一个块
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def mapper():
    """
    Mapper 函数
    从标准输入读取文本，分块后输出
    """
    try:
        # 从标准输入读取数据（格式：文件路径 \t 文本内容）
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            # 分割文件路径和文本内容
            parts = line.split('\t', 1)
            if len(parts) < 2:
                logger.warning("输入格式错误，跳过: {}".format(line))
                continue
            
            file_path = parts[0]
            text = parts[1]
            
            logger.info("分块处理: {}".format(file_path))
            
            # 分块
            chunks = split_into_chunks(text, chunk_size=1000)
            
            # 输出：文件路径_块编号 \t 文本块
            for i, chunk in enumerate(chunks):
                chunk_key = "{}_chunk_{}".format(file_path, i)
                output = "{}\t{}".format(chunk_key, chunk)
                print(output)
            
            logger.info("文件 {} 分为 {} 块".format(file_path, len(chunks)))
            
    except Exception as e:
        logger.error("Mapper 执行出错: {}".format(e))
        sys.stderr.write("ERROR: {}\n".format(e))
        sys.exit(1)


if __name__ == "__main__":
    mapper()


