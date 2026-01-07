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
    合并同一文件的文本内容（如果有多个分片）
    输出格式：文件路径 \t 完整文本内容
    """
    try:
        current_file = None
        text_parts = []
        processed_count = 0
        error_count = 0
        
        # 从标准输入读取数据（格式：文件路径 \t 文本内容）
        # 使用二进制模式读取，然后解码，避免编码问题
        import io
        try:
            # Python 3: 尝试使用 buffer 属性
            stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
        except AttributeError:
            # 如果没有 buffer 属性，直接使用 sys.stdin
            stdin = sys.stdin
        
        for line in stdin:
            try:
                # 移除所有类型的换行符和空白字符
                line = line.rstrip('\r\n').strip()
                if not line:
                    continue
                
                # 分割文件路径和文本内容
                parts = line.split('\t', 1)
                if len(parts) < 2:
                    # 如果没有制表符，记录警告但尝试继续
                    logger.warning("输入格式可能错误，跳过: {}".format(line[:100] if len(line) > 100 else line))
                    sys.stderr.write("WARNING: Invalid input format, skipping line: {}\n".format(line[:100]))
                    error_count += 1
                    continue
                
                file_path = parts[0].strip()
                text_content = parts[1]
                
                # 如果是新文件，输出上一个文件的完整文本
                if current_file is not None and current_file != file_path:
                    # 合并文本内容
                    full_text = '\n\n'.join(text_parts)
                    output = "{}\t{}".format(current_file, full_text)
                    print(output)
                    sys.stdout.flush()
                    processed_count += 1
                    logger.info("输出文件: {}, 文本长度: {}".format(current_file, len(full_text)))
                    text_parts = []
                
                current_file = file_path
                # 如果文本内容以ERROR开头，仍然添加，但记录警告
                if text_content.startswith("ERROR:"):
                    logger.warning("文件包含错误标记: {}, 内容: {}".format(file_path, text_content[:100]))
                text_parts.append(text_content)
                
            except Exception as line_error:
                # 处理单行错误，继续处理其他行
                error_count += 1
                logger.warning("处理行时出错: {}, 错误: {}".format(line[:100] if line else "空行", line_error))
                # 向 stderr 输出时注意编码问题，避免 ASCII 编码错误导致进程退出
                msg = "WARNING: Line processing error: {}\n".format(line_error)
                try:
                    if hasattr(sys.stderr, "buffer"):
                        sys.stderr.buffer.write(msg.encode("utf-8", "replace"))
                    else:
                        sys.stderr.write(msg)
                except Exception:
                    safe_msg = msg.encode("ascii", "replace").decode("ascii")
                    try:
                        sys.stderr.write(safe_msg)
                    except Exception:
                        pass
                continue
        
        # 输出最后一个文件的完整文本
        if current_file is not None:
            full_text = '\n\n'.join(text_parts)
            output = "{}\t{}".format(current_file, full_text)
            print(output)
            sys.stdout.flush()
            processed_count += 1
            logger.info("输出最后一个文件: {}, 文本长度: {}".format(current_file, len(full_text)))
        
        logger.info("Reducer 完成: 成功处理 {} 个文件, 跳过 {} 个错误行".format(processed_count, error_count))
            
    except Exception as e:
        logger.error("Reducer 执行出错: {}".format(e), exc_info=True)
        msg = "ERROR: {}\n".format(e)
        try:
            if hasattr(sys.stderr, "buffer"):
                sys.stderr.buffer.write(msg.encode("utf-8", "replace"))
            else:
                sys.stderr.write(msg)
        except Exception:
            safe_msg = msg.encode("ascii", "replace").decode("ascii")
            try:
                sys.stderr.write(safe_msg)
            except Exception:
                pass
        import traceback
        traceback.print_exc(file=sys.stderr)
        # 注意：这里不再 sys.exit(1)，避免 reducer 以非零状态让 Streaming 任务整体失败


if __name__ == "__main__":
    reducer()


