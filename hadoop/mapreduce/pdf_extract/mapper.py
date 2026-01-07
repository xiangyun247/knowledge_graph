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
import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LOG_HDFS_DIR = "/knowledge_graph/logs"
LOG_HDFS_FILE = LOG_HDFS_DIR + "/pdf_extract_errors.log"


def _get_hadoop_bin():
    """
    获取 hadoop 可执行文件路径
    """
    hadoop_cmd = os.environ.get('HADOOP_HOME', '/opt/hadoop-3.2.1')
    hadoop_bin = os.path.join(hadoop_cmd, 'bin', 'hadoop')
    if not os.path.exists(hadoop_bin):
        hadoop_bin = 'hadoop'
    return hadoop_bin


def log_error_to_hdfs(message):
    """
    将错误信息写入 HDFS 日志文件，便于任务结束后排查问题。
    使用 appendToFile 追加写入。
    """
    try:
        import subprocess

        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        full_message = "[{}] {}\n".format(timestamp, message)

        hadoop_bin = _get_hadoop_bin()

        # 确保日志目录存在
        subprocess.run(
            [hadoop_bin, "fs", "-mkdir", "-p", LOG_HDFS_DIR],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 使用 echo 管道到 hadoop fs -appendToFile
        proc = subprocess.Popen(
            [hadoop_bin, "fs", "-appendToFile", "-", LOG_HDFS_FILE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate(input=full_message.encode("utf-8", "replace"))
    except Exception as e:
        # 如果写 HDFS 失败，只在本地日志里记一条，不再抛错影响主流程
        logger.error("写入 HDFS 日志失败: %s", e)


try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.error("pdfplumber 未安装，无法提取 PDF 文本")


def extract_pdf_text(hdfs_path: str) -> str:
    """
    从 HDFS 下载 PDF 文件并提取文本
    
    Args:
        hdfs_path: HDFS 中的 PDF 文件路径
        
    Returns:
        提取的文本内容
    """
    if not PDFPLUMBER_AVAILABLE:
        msg = "pdfplumber 未安装"
        logger.error(msg)
        log_error_to_hdfs("pdfplumber 未安装, 无法处理文件: {}".format(hdfs_path))
        return "ERROR: " + msg
    
    import tempfile
    import subprocess
    
    # 清理HDFS路径（移除可能的换行符和空白）
    hdfs_path = hdfs_path.strip()
    if not hdfs_path:
        return "ERROR: HDFS路径为空"
    
    # 创建临时文件
    temp_file = None
    try:
        # 创建临时目录（使用系统临时目录）
        temp_dir = os.environ.get('TMPDIR', '/tmp')
        if not os.path.exists(temp_dir):
            temp_dir = '/tmp'
        
        # 从文件名生成临时文件名
        import hashlib
        path_hash = hashlib.md5(hdfs_path.encode('utf-8')).hexdigest()[:8]
        temp_file = os.path.join(temp_dir, 'pdf_extract_{}.pdf'.format(path_hash))
        
        logger.info("从 HDFS 下载文件: {} -> {}".format(hdfs_path, temp_file))
        
        # 使用 hadoop fs -get 下载文件
        # 确保hadoop命令在PATH中
        hadoop_cmd = os.environ.get('HADOOP_HOME', '/opt/hadoop-3.2.1')
        hadoop_bin = os.path.join(hadoop_cmd, 'bin', 'hadoop')
        if not os.path.exists(hadoop_bin):
            hadoop_bin = 'hadoop'  # 回退到系统PATH中的hadoop命令
        
        result = subprocess.run(
            [hadoop_bin, 'fs', '-get', hdfs_path, temp_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # Python 3.5 兼容
            timeout=300,
            env=os.environ.copy()
        )
        
        if result.returncode != 0:
            error_msg = "HDFS 下载失败 (返回码: {}): {}".format(result.returncode, result.stderr)
            logger.error(error_msg)
            log_error_to_hdfs("从 HDFS 下载文件失败: path={}, error={}".format(hdfs_path, error_msg))
            # 尝试使用完整路径
            if hadoop_bin != 'hadoop':
                logger.info("尝试使用系统hadoop命令")
                result2 = subprocess.run(
                    ['hadoop', 'fs', '-get', hdfs_path, temp_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=300
                )
                if result2.returncode != 0:
                    log_error_to_hdfs(
                        "使用系统 hadoop 命令下载失败: path={}, error={}".format(
                            hdfs_path, result2.stderr
                        )
                    )
                    return "ERROR: {}".format(result2.stderr)
            else:
                log_error_to_hdfs("HDFS 下载失败且未重试系统 hadoop: path={}, error={}".format(hdfs_path, error_msg))
                return "ERROR: {}".format(error_msg)
        
        # 检查文件是否存在
        if not os.path.exists(temp_file):
            msg = "下载的文件不存在: {}".format(temp_file)
            log_error_to_hdfs("HDFS 下载的文件不存在: path={}, local={}".format(hdfs_path, temp_file))
            return "ERROR: " + msg
        
        # 提取 PDF 文本
        text_parts = []
        try:
            with pdfplumber.open(temp_file) as pdf:
                logger.info("处理 PDF 文件: {}，共 {} 页".format(hdfs_path, len(pdf.pages)))
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text() or ""
                        # 清理文本
                        page_text = page_text.replace("\u00a0", " ")
                        text_parts.append(page_text)
                    except Exception as page_error:
                        logger.warning("提取第 {} 页失败: {}".format(i+1, page_error))
                        text_parts.append("")  # 添加空字符串以保持页数一致
        except Exception as pdf_error:
            logger.error("打开PDF文件失败: {}".format(pdf_error))
            log_error_to_hdfs("打开 PDF 失败: path={}, error={}".format(hdfs_path, pdf_error))
            return "ERROR: 无法打开PDF文件: {}".format(str(pdf_error))
        
        full_text = "\n\n".join(text_parts)
        logger.info("PDF 文本提取完成，总长度 {} 字符".format(len(full_text)))
        return full_text
        
    except Exception as e:
        logger.error("提取 PDF 文本失败: {}, 错误: {}".format(hdfs_path, e), exc_info=True)
        log_error_to_hdfs("提取 PDF 文本失败: path={}, error={}".format(hdfs_path, e))
        return "ERROR: {}".format(str(e))
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception as cleanup_error:
                logger.warning("清理临时文件失败: {}".format(cleanup_error))


def mapper():
    """
    Mapper 函数
    Hadoop Streaming 会将输入文件的内容传递给 mapper
    
    输入格式：HDFS 文件路径（每行一个路径）
    输出格式：文件路径 \t 文本内容
    """
    try:
        # 从标准输入读取 HDFS 文件路径列表
        # 使用二进制模式读取，然后解码，避免编码问题
        import io
        try:
            # Python 3: 尝试使用 buffer 属性
            stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
        except AttributeError:
            # 如果没有 buffer 属性，直接使用 sys.stdin
            stdin = sys.stdin
        
        processed_count = 0
        error_count = 0
        
        for line in stdin:
            try:
                # 清理输入行（移除换行符和空白）
                file_path = line.rstrip('\r\n').strip()
                if not file_path:
                    continue
                
                # 跳过注释行
                if file_path.startswith('#'):
                    continue
                
                logger.info("处理文件: {}".format(file_path))
                
                # 提取 PDF 文本
                text = extract_pdf_text(file_path)
                
                # 如果提取失败，输出错误但继续处理其他文件
                if text.startswith("ERROR:"):
                    error_count += 1
                    logger.error("文件处理失败: {}, {}".format(file_path, text))
                    # 仍然输出，但标记为错误，让reducer可以处理
                    output = "{}\t{}".format(file_path, text)
                    print(output)
                    sys.stdout.flush()
                    continue
                
                # 输出：文件路径 \t 文本内容
                # 使用制表符分隔，便于 Reducer 处理
                output = "{}\t{}".format(file_path, text)
                print(output)
                sys.stdout.flush()  # 确保输出立即刷新
                
                processed_count += 1
                logger.info("文件处理完成: {}, 文本长度: {}".format(file_path, len(text)))
                
            except Exception as line_error:
                error_count += 1
                logger.error("处理行时出错: {}, 错误: {}".format(line[:100] if line else "空行", line_error))
                # 向 stderr 输出时注意编码问题，避免 ASCII 编码错误导致进程直接退出
                msg = "ERROR: Line processing failed: {}\n".format(line_error)
                try:
                    # 优先使用二进制写入，使用 UTF-8 编码并替换无法编码的字符
                    if hasattr(sys.stderr, "buffer"):
                        sys.stderr.buffer.write(msg.encode("utf-8", "replace"))
                    else:
                        sys.stderr.write(msg)
                except Exception:
                    # 如果仍然失败，退回到 ASCII 可打印字符
                    safe_msg = msg.encode("ascii", "replace").decode("ascii")
                    try:
                        sys.stderr.write(safe_msg)
                    except Exception:
                        # 最后退路，什么也不做，避免影响主流程
                        pass
                continue
        
        logger.info("Mapper 完成: 成功处理 {} 个文件, 失败 {} 个文件".format(processed_count, error_count))
        
    except Exception as e:
        logger.error("Mapper 执行出错: {}".format(e), exc_info=True)
        msg = "ERROR: {}\n".format(e)
        try:
            # 优先使用二进制写入，避免编码问题导致进程异常退出
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
        # 注意：这里不再 sys.exit(1)，避免 mapper 非零退出码导致 Streaming 任务整体失败


if __name__ == "__main__":
    mapper()


