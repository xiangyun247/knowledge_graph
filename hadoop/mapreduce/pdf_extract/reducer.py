#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 文本提取 Reducer
用于 Hadoop MapReduce 任务

合并同一个文件的文本内容（如果有多个分片）
输出格式：文件路径 \t 完整文本内容
"""

import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def reducer():
    """
    Reducer 函数
    合并同一文件的文本内容
    """
    try:
        current_file = None
        text_parts = []
        
        # 从标准输入读取数据（格式：文件路径 \t 文本内容）
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            # 分割文件路径和文本内容
            parts = line.split('\t', 1)
            if len(parts) < 2:
                logger.warning(f"输入格式错误，跳过: {line}")
                continue
            
            file_path = parts[0]
            text_content = parts[1]
            
            # 如果是新文件，输出上一个文件的完整文本
            if current_file is not None and current_file != file_path:
                full_text = ' '.join(text_parts)
                output = f"{current_file}\t{full_text}"
                print(output)
                text_parts = []
            
            current_file = file_path
            text_parts.append(text_content)
        
        # 输出最后一个文件的完整文本
        if current_file is not None:
            full_text = ' '.join(text_parts)
            output = f"{current_file}\t{full_text}"
            print(output)
            
    except Exception as e:
        logger.error(f"Reducer 执行出错: {e}")
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    reducer()


