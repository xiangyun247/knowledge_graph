#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hadoop 服务封装
"""

import os
import subprocess
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 全局 Hadoop 服务实例
_hadoop_service_instance = None


class HadoopService:
    """Hadoop 服务类"""
    
    def __init__(self):
        self.hadoop_namenode = os.getenv("HADOOP_NAMENODE", "hadoop-namenode:9000")
        self.hadoop_home = os.getenv("HADOOP_HOME", "/opt/hadoop-3.2.1")
        self.hdfs_root = "/knowledge_graph"
        
        logger.info(f"Hadoop 服务初始化: NameNode={self.hadoop_namenode}, HDFS_ROOT={self.hdfs_root}")
    
    def upload_file_to_hdfs(self, content: bytes, filename: str) -> str:
        """
        上传单个文件到 HDFS
        
        Args:
            content: 文件内容(字节)
            filename: 文件名
            
        Returns:
            HDFS 路径
        """
        # 保存到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # 上传到 HDFS
            hdfs_path = f"{self.hdfs_root}/uploads/{filename}"
            cmd = [
                "hadoop", "fs", "-put",
                "-f", tmp_path, hdfs_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"HDFS 上传失败: {result.stderr}")
            
            logger.info(f"文件已上传到 HDFS: {hdfs_path}")
            return hdfs_path
        finally:
            # 删除临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def upload_files_to_hdfs(self, file_paths: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        批量上传文件到 HDFS
        
        Args:
            file_paths: 文件路径列表,每个元素包含:
                - file_id: 文件ID
                - local_path: 本地文件路径
                - filename: 文件名
                
        Returns:
            上传结果,包含:
                - success_count: 成功数量
                - failed_count: 失败数量
                - success_files: 成功文件列表
                - failed_files: 失败文件列表
        """
        success_count = 0
        failed_count = 0
        success_files = []
        failed_files = []
        
        for file_info in file_paths:
            file_id = file_info.get("file_id")
            local_path = file_info.get("local_path")
            filename = file_info.get("filename")
            
            try:
                if not os.path.exists(local_path):
                    raise Exception(f"本地文件不存在: {local_path}")
                
                # 上传到 HDFS
                hdfs_path = f"{self.hdfs_root}/uploads/{file_id}/{filename}"
                
                # 确保 HDFS 目录存在
                dir_cmd = ["hadoop", "fs", "-mkdir", "-p", f"{self.hdfs_root}/uploads/{file_id}"]
                subprocess.run(dir_cmd, capture_output=True, timeout=30)
                
                # 上传文件
                cmd = ["hadoop", "fs", "-put", "-f", local_path, hdfs_path]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    success_count += 1
                    success_files.append({
                        "file_id": file_id,
                        "filename": filename,
                        "hdfs_path": hdfs_path
                    })
                    logger.info(f"文件上传成功: {filename} -> {hdfs_path}")
                else:
                    raise Exception(f"HDFS 上传失败: {result.stderr}")
                    
            except Exception as e:
                failed_count += 1
                failed_files.append({
                    "file_id": file_id,
                    "filename": filename,
                    "error": str(e)
                })
                logger.error(f"文件上传失败: {filename}, 错误: {e}")
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "success_files": success_files,
            "failed_files": failed_files
        }
    
    def process_files_with_hadoop(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        使用 Hadoop MapReduce 处理文件
        
        流程:
        1. PDF 提取 (pdf_extract)
        2. 文本清洗 (text_clean)
        3. 文本分块 (text_chunk)
        
        Args:
            file_ids: 文件ID列表
            
        Returns:
            处理结果,包含:
                - success: 是否成功
                - final_output: 最终输出路径
                - error: 错误信息(如果有)
        """
        try:
            logger.info(f"开始 Hadoop 处理,文件数量: {len(file_ids)}")
            
            # 阶段1: PDF 提取
            pdf_output = self._run_pdf_extract(file_ids)
            if not pdf_output.get("success"):
                return {
                    "success": False,
                    "error": f"PDF提取失败: {pdf_output.get('error')}"
                }
            
            # 阶段2: 文本清洗
            clean_output = self._run_text_clean(pdf_output["output_path"])
            if not clean_output.get("success"):
                return {
                    "success": False,
                    "error": f"文本清洗失败: {clean_output.get('error')}"
                }
            
            # 阶段3: 文本分块
            chunk_output = self._run_text_chunk(clean_output["output_path"])
            if not chunk_output.get("success"):
                return {
                    "success": False,
                    "error": f"文本分块失败: {chunk_output.get('error')}"
                }
            
            logger.info(f"Hadoop 处理完成,最终输出: {chunk_output['output_path']}")
            
            return {
                "success": True,
                "final_output": chunk_output["output_path"],
                "stages": {
                    "pdf_extract": pdf_output,
                    "text_clean": clean_output,
                    "text_chunk": chunk_output
                }
            }
            
        except Exception as e:
            logger.error(f"Hadoop 处理失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _run_pdf_extract(self, file_ids: List[str]) -> Dict[str, Any]:
        """运行 PDF 提取任务"""
        try:
            input_path = f"{self.hdfs_root}/uploads"
            output_path = f"{self.hdfs_root}/processed/pdf_extract"
            
            mapper = "hadoop/mapreduce/pdf_extract/mapper.py"
            reducer = "hadoop/mapreduce/pdf_extract/reducer.py"
            
            return self._submit_streaming_job(
                input_path=input_path,
                output_path=output_path,
                mapper=mapper,
                reducer=reducer,
                job_name="PDF提取"
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_text_clean(self, input_path: str) -> Dict[str, Any]:
        """运行文本清洗任务"""
        try:
            output_path = f"{self.hdfs_root}/processed/text_clean"
            mapper = "hadoop/mapreduce/text_clean/mapper.py"
            
            return self._submit_streaming_job(
                input_path=input_path,
                output_path=output_path,
                mapper=mapper,
                reducer=None,
                job_name="文本清洗"
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_text_chunk(self, input_path: str) -> Dict[str, Any]:
        """运行文本分块任务"""
        try:
            output_path = f"{self.hdfs_root}/processed/text_chunk"
            mapper = "hadoop/mapreduce/text_chunk/mapper.py"
            
            return self._submit_streaming_job(
                input_path=input_path,
                output_path=output_path,
                mapper=mapper,
                reducer=None,
                job_name="文本分块"
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _submit_streaming_job(
        self,
        input_path: str,
        output_path: str,
        mapper: str,
        reducer: Optional[str] = None,
        job_name: str = "Hadoop任务"
    ) -> Dict[str, Any]:
        """
        提交 Hadoop Streaming 任务
        
        Args:
            input_path: 输入路径
            output_path: 输出路径
            mapper: Mapper 脚本路径
            reducer: Reducer 脚本路径(可选)
            job_name: 任务名称
            
        Returns:
            任务结果
        """
        try:
            logger.info(f"提交 {job_name} 任务: {input_path} -> {output_path}")
            
            # 删除已存在的输出目录
            subprocess.run(
                ["hadoop", "fs", "-rm", "-r", "-f", output_path],
                capture_output=True,
                timeout=30
            )
            
            # 上传脚本到 HDFS
            mapper_hdfs = self._upload_script_to_hdfs(mapper)
            reducer_hdfs = None
            if reducer:
                reducer_hdfs = self._upload_script_to_hdfs(reducer)
            
            # 构建命令
            cmd = [
                "hadoop", "jar",
                f"{self.hadoop_home}/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar",
                "-input", input_path,
                "-output", output_path,
                "-mapper", f"python3 {mapper_hdfs}",
                "-file", mapper_hdfs,
            ]
            
            if reducer_hdfs:
                cmd.extend(["-reducer", f"python3 {reducer_hdfs}", "-file", reducer_hdfs])
            
            # 设置 Python 环境
            cmd.extend([
                "-cmdenv", f"PYTHONPATH={self.hadoop_home}",
                "-cmdenv", "HADOOP_MAPRED_HOME=/opt/hadoop-3.2.1",
            ])
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 提交任务
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"{job_name} 任务失败: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "output_path": None
                }
            
            logger.info(f"{job_name} 任务完成: {output_path}")
            
            return {
                "success": True,
                "output_path": output_path,
                "job_id": None  # Streaming 任务没有 job ID
            }
            
        except Exception as e:
            logger.error(f"提交 {job_name} 任务失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "output_path": None
            }
    
    def _upload_script_to_hdfs(self, script_path: str) -> str:
        """
        上传脚本到 HDFS
        
        Args:
            script_path: 本地脚本路径
            
        Returns:
            HDFS 路径
        """
        script_name = os.path.basename(script_path)
        hdfs_path = f"{self.hdfs_root}/scripts/{script_name}"
        
        # 确保目录存在
        subprocess.run(
            ["hadoop", "fs", "-mkdir", "-p", f"{self.hdfs_root}/scripts"],
            capture_output=True,
            timeout=30
        )
        
        # 上传脚本
        subprocess.run(
            ["hadoop", "fs", "-put", "-f", script_path, hdfs_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return hdfs_path


def get_hadoop_service() -> HadoopService:
    """
    获取 Hadoop 服务实例(单例模式)
    
    Returns:
        HadoopService 实例
    """
    global _hadoop_service_instance
    
    if _hadoop_service_instance is None:
        _hadoop_service_instance = HadoopService()
    
    return _hadoop_service_instance

