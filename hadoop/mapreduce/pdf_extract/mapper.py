#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 文本提取 Mapper
用于 Hadoop MapReduce 任务

从 HDFS 读取 PDF 文件，提取文本内容
输出格式：文件路径 	 文本内容
"""

# 确保脚本在各种环境下都能正常运行
import sys
import os
import logging
import datetime

# 确保Python版本兼容
if sys.version_info < (3, 6):
    print("ERROR: Python 3.6+ is required", file=sys.stderr)
    # 注意：这里不能使用sys.exit(1)，否则会导致Hadoop任务失败
    # 改为返回错误信息并继续执行
    pass

# 添加详细的调试信息
print(f"[DEBUG] Python版本: {sys.version}", file=sys.stderr)
print(f"[DEBUG] 脚本路径: {os.path.abspath(__file__)}", file=sys.stderr)
print(f"[DEBUG] 当前工作目录: {os.getcwd()}", file=sys.stderr)
print(f"[DEBUG] 环境变量HADOOP_HOME: {os.environ.get('HADOOP_HOME', '未设置')}", file=sys.stderr)
print(f"[DEBUG] 环境变量PYTHONPATH: {os.environ.get('PYTHONPATH', '未设置')}", file=sys.stderr)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 使用本地日志，避免HDFS操作导致的额外失败风险
# HDFS日志将由上层应用或Hadoop本身处理
LOG_LOCAL_FILE = "/tmp/pdf_extract_mapper.log"

# 配置日志文件输出
file_handler = logging.FileHandler(LOG_LOCAL_FILE, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 保持控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)


def log_error(message):
    """
    将错误信息写入本地日志文件
    """
    logger.error(message)


# 尝试导入pdfplumber，如果未安装，设置标志为False
# 这样即使pdfplumber未安装，脚本也能正常运行，只是返回错误信息
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    logger.info("pdfplumber 导入成功")
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.error("pdfplumber 未安装")


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
        logger.error("pdfplumber 未安装, 无法处理文件: %s", hdfs_path)
        return "ERROR: " + msg
    
    import tempfile
    import subprocess
    import shutil
    
    # 清理HDFS路径（移除可能的换行符和空白）
    hdfs_path = hdfs_path.strip()
    if not hdfs_path:
        return "ERROR: HDFS路径为空"
    
    # 创建临时文件
    temp_file = None
    try:
        # 使用tempfile模块创建临时文件，确保在各种操作系统上都能正常工作
        import tempfile
        import hashlib
        
        # 获取系统临时目录
        temp_dir = tempfile.gettempdir()
        logger.info("使用临时目录: %s", temp_dir)
        
        # 从文件名生成临时文件名
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
            logger.error("从 HDFS 下载文件失败: path=%s, error=%s", hdfs_path, error_msg)
            # 尝试使用完整路径
            if hadoop_bin != 'hadoop':
                logger.info("尝试使用系统hadoop命令")
                result2 = subprocess.run(
                    ['hadoop', 'fs', '-get', hdfs_path, temp_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=300,
                    env=os.environ.copy()
                )
                if result2.returncode != 0:
                    logger.error("使用系统 hadoop 命令下载失败: path=%s, error=%s", hdfs_path, result2.stderr)
                    return "ERROR: {}".format(result2.stderr)
            else:
                logger.error("HDFS 下载失败且未重试系统 hadoop: path=%s, error=%s", hdfs_path, error_msg)
                return "ERROR: {}".format(error_msg)
        
        # 检查文件是否存在
        if not os.path.exists(temp_file):
            msg = "下载的文件不存在: {}".format(temp_file)
            logger.error("HDFS 下载的文件不存在: path=%s, local=%s", hdfs_path, temp_file)
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
            import traceback
            error_detail = traceback.format_exc()
            error_type = type(pdf_error).__name__
            # 确保错误信息完整，优先使用str()，如果为空则使用repr()，如果还是有问题则使用异常类型
            try:
                error_msg = str(pdf_error) if pdf_error else ""
                if not error_msg:
                    error_msg = repr(pdf_error) if pdf_error else ""
                if not error_msg or len(error_msg) < 3:
                    error_msg = f"{error_type} exception occurred"
            except Exception:
                error_msg = f"{error_type} exception occurred (unable to get message)"
            
            logger.error("打开PDF文件失败: %s (%s), 详细错误: %s", error_msg, error_type, error_detail)
            logger.error("打开 PDF 失败: path=%s, error_type=%s, error=%s, detail=%s",
                hdfs_path, error_type, error_msg[:200], error_detail[:500])
            return "ERROR: 无法打开PDF文件: {} ({})".format(error_msg[:200], error_type)
        
        full_text = "\n\n".join(text_parts)
        logger.info("PDF 文本提取完成，总长度 {} 字符".format(len(full_text)))
        return full_text
        
    except Exception as e:
        logger.error("提取 PDF 文本失败: %s, 错误: %s", hdfs_path, e, exc_info=True)
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
    # 初始化计数
    processed_count = 0
    error_count = 0
    
    try:
        # 从标准输入读取 HDFS 文件路径列表
        # 简化输入处理，直接使用sys.stdin，确保在各种环境下都能正常工作
        print("[DEBUG] 开始读取标准输入", file=sys.stderr)
        
        # 读取所有行，避免逐行读取的缓冲问题
        import sys
        lines = sys.stdin.readlines()
        print(f"[DEBUG] 读取到 {len(lines)} 行输入", file=sys.stderr)
        
        for line in lines:
            try:
                # 清理输入行（移除换行符和空白）
                file_path = line.rstrip('\r\n').strip()
                if not file_path:
                    continue
                
                # 跳过注释行
                if file_path.startswith('#'):
                    continue
                
                print(f"[DEBUG] 处理文件: {file_path}", file=sys.stderr)
                
                # 提取 PDF 文本
                text = extract_pdf_text(file_path)
                
                # 确保输出格式正确，避免出现空输出
                if not text:
                    text = "ERROR: 提取的文本为空"
                
                # 无论成功失败，都输出结果，避免Hadoop Streaming管道错误
                output = f"{file_path}\t{text}"
                
                # 使用print函数输出，确保换行符正确
                print(output)
                # 立即刷新输出，避免缓冲区问题
                sys.stdout.flush()
                
                if text.startswith("ERROR:"):
                    error_count += 1
                    print(f"[DEBUG] 文件处理失败: {file_path}, {text}", file=sys.stderr)
                else:
                    processed_count += 1
                    print(f"[DEBUG] 文件处理完成: {file_path}, 文本长度: {len(text)}", file=sys.stderr)
                    
            except Exception as line_error:
                error_count += 1
                error_msg = f"ERROR: Line processing failed: {line_error}"
                print(f"[DEBUG] {error_msg}", file=sys.stderr)
                # 输出错误信息，确保管道不会被关闭
                print(f"{line.rstrip('\r\n').strip()}\t{error_msg}")
                sys.stdout.flush()
                continue
        
        print(f"[DEBUG] Mapper 完成: 成功处理 {processed_count} 个文件, 失败 {error_count} 个文件", file=sys.stderr)
        
    except Exception as e:
        error_msg = f"ERROR: Mapper execution failed: {e}"
        print(f"[DEBUG] {error_msg}", file=sys.stderr)
        # 输出错误信息，确保管道不会被关闭
        print(f"ERROR\t{error_msg}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc(file=sys.stderr)
    
    # 最终结果统计
    print(f"[DEBUG] Mapper 最终统计: 成功 {processed_count}, 失败 {error_count}", file=sys.stderr)


if __name__ == "__main__":
    # 输出脚本启动信息到stderr，确保在Hadoop日志中可见
    print("=== PDF 文本提取 Mapper 启动 ===", file=sys.stderr)
    print(f"Python 版本: {sys.version}", file=sys.stderr)
    print(f"操作系统: {sys.platform}", file=sys.stderr)
    print(f"当前目录: {os.getcwd()}", file=sys.stderr)
    print(f"HADOOP_HOME: {os.environ.get('HADOOP_HOME', '未设置')}", file=sys.stderr)
    
    try:
        # 捕获所有异常，确保进程不会以非零退出码结束
        mapper()
    except Exception as e:
        print(f"[ERROR] 未捕获的异常: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # 输出一个默认的错误结果，确保管道不会被关闭
        print(f"ERROR\t未捕获的异常: {e}")
        sys.stdout.flush()
    finally:
        print("=== PDF 文本提取 Mapper 结束 ===", file=sys.stderr)
        # 强制进程以退出码0结束，无论之前发生了什么错误
        # 这样可以确保Hadoop任务不会因为Mapper进程退出码而失败
        # 任务的成功与否应该由输出结果来决定，而不是进程退出码
        sys.exit(0)


