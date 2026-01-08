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
        self.hadoop_namenode = os.getenv("HADOOP_NAMENODE", "hadoop-namenode:8020")
        self.hadoop_home = os.getenv("HADOOP_HOME", "/opt/hadoop-3.2.1")
        self.hdfs_root = "/knowledge_graph"
        
        # 动态查找 streaming jar（兼容不同版本和路径）
        self.streaming_jar = self._find_streaming_jar()
        
        logger.info(f"Hadoop 服务初始化: NameNode={self.hadoop_namenode}, HDFS_ROOT={self.hdfs_root}, StreamingJAR={self.streaming_jar}")
    
    def _find_streaming_jar(self) -> str:
        """查找 Hadoop Streaming JAR 文件路径"""
        # 可能的路径列表
        possible_paths = [
            f"{self.hadoop_home}/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar",
            f"{self.hadoop_home}/share/hadoop/tools/lib/hadoop-streaming.jar",
            "/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar",
            "/opt/hadoop/share/hadoop/tools/lib/hadoop-streaming.jar",
        ]
        
        # 尝试在容器中查找
        for jar_path in possible_paths:
            try:
                result = subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "test", "-f", jar_path],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"找到 Streaming JAR: {jar_path}")
                    return jar_path
            except Exception as e:
                logger.debug(f"检查路径 {jar_path} 失败: {e}")
        
        # 如果找不到，使用默认路径（让 Hadoop 自己处理）
        default_path = f"{self.hadoop_home}/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar"
        logger.warning(f"未找到 Streaming JAR，使用默认路径: {default_path}")
        return default_path
    
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
                "docker", "exec", "hadoop-namenode",
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
                dir_cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-mkdir", "-p", f"{self.hdfs_root}/uploads/{file_id}"]
                dir_result = subprocess.run(dir_cmd, capture_output=True, text=True, timeout=30)
                if dir_result.returncode != 0:
                    logger.warning(f"创建目录可能失败: {dir_result.stderr}")
                
                # 先将文件复制到容器内的临时目录（解决 Windows 路径问题）
                container_temp_path = f"/tmp/{file_id}_{filename}"
                copy_result = subprocess.run(
                    ["docker", "cp", local_path, f"hadoop-namenode:{container_temp_path}"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if copy_result.returncode != 0:
                    raise Exception(f"复制文件到容器失败: {copy_result.stderr}")
                
                # 从容器内的临时路径上传到 HDFS
                cmd = [
                    "docker", "exec", "hadoop-namenode",
                    "hadoop", "fs", "-put", "-f", container_temp_path, hdfs_path
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                # 清理容器内的临时文件
                subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "rm", "-f", container_temp_path],
                    capture_output=True,
                    timeout=10
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
            # 创建输入文件列表（包含所有要处理的 PDF 文件路径）
            input_list_path = f"{self.hdfs_root}/temp/input_list_{int(time.time())}.txt"
            
            # 收集所有 PDF 文件路径
            pdf_paths = []
            for file_id in file_ids:
                # 列出该 file_id 目录下的所有文件
                list_cmd = [
                    "docker", "exec", "hadoop-namenode",
                    "hadoop", "fs", "-ls", f"{self.hdfs_root}/uploads/{file_id}"
                ]
                result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    # 解析输出，提取文件路径
                    for line in result.stdout.split('\n'):
                        if '.pdf' in line.lower():
                            # 提取文件路径（最后一列）
                            parts = line.split()
                            if len(parts) >= 8:
                                file_path = parts[-1]
                                pdf_paths.append(file_path)
            
            if not pdf_paths:
                return {"success": False, "error": "未找到要处理的 PDF 文件"}
            
            # 创建输入列表文件（本地临时文件）
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
                for pdf_path in pdf_paths:
                    tmp_file.write(f"{pdf_path}\n")
                tmp_list_path = tmp_file.name
            
            try:
                # 确保 HDFS temp 目录存在
                mkdir_cmd = [
                    "docker", "exec", "hadoop-namenode",
                    "hadoop", "fs", "-mkdir", "-p", f"{self.hdfs_root}/temp"
                ]
                mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)
                if mkdir_result.returncode != 0:
                    logger.warning(f"创建 temp 目录可能失败: {mkdir_result.stderr}")
                
                # 上传输入列表到 HDFS
                container_temp = f"/tmp/input_list_{int(time.time())}.txt"
                copy_result = subprocess.run(
                    ["docker", "cp", tmp_list_path, f"hadoop-namenode:{container_temp}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if copy_result.returncode != 0:
                    raise Exception(f"复制输入列表到容器失败: {copy_result.stderr}")
                
                put_result = subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-put", "-f", container_temp, input_list_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if put_result.returncode != 0:
                    raise Exception(f"上传输入列表到 HDFS 失败: {put_result.stderr}")
                
                # 验证文件是否上传成功
                verify_result = subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-test", "-e", input_list_path],
                    capture_output=True,
                    timeout=10
                )
                if verify_result.returncode != 0:
                    raise Exception(f"输入列表文件验证失败，文件可能不存在: {input_list_path}")
                
                logger.info(f"输入列表已上传到 HDFS: {input_list_path}，包含 {len(pdf_paths)} 个文件")
                
                # 清理容器内临时文件
                subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "rm", "-f", container_temp],
                    capture_output=True,
                    timeout=10
                )
            finally:
                # 清理本地临时文件
                if os.path.exists(tmp_list_path):
                    os.unlink(tmp_list_path)
            
            output_path = f"{self.hdfs_root}/processed/pdf_extract"
            
            # 使用Shell脚本作为Mapper，避免Python依赖问题
            mapper = "hadoop/mapreduce/pdf_extract/mapper_shell.sh"
            reducer = "hadoop/mapreduce/pdf_extract/reducer.py"
            
            return self._submit_streaming_job(
                input_path=input_list_path,  # 使用文件列表作为输入
                output_path=output_path,
                mapper=mapper,
                reducer=reducer,
                job_name="PDF提取"
            )
        except Exception as e:
            logger.error(f"PDF 提取任务失败: {e}", exc_info=True)
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
                [ "docker", "exec", "hadoop-namenode","hadoop", "fs", "-rm", "-r", "-f", output_path],
                capture_output=True,
                timeout=30
            )
            
            # 上传脚本到 HDFS
            mapper_hdfs = self._upload_script_to_hdfs(mapper)
            reducer_hdfs = None
            if reducer:
                reducer_hdfs = self._upload_script_to_hdfs(reducer)
            
            # Hadoop Streaming 的 -file 参数需要本地文件系统路径
            # 需要先将 HDFS 中的脚本下载到容器内的临时目录
            mapper_name = os.path.basename(mapper)
            reducer_name = os.path.basename(reducer) if reducer else None
            
            mapper_local = f"/tmp/{mapper_name}"
            reducer_local = f"/tmp/{reducer_name}" if reducer_name else None
            
            # 从 HDFS 下载脚本到容器本地
            download_cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-get", mapper_hdfs, mapper_local]
            download_result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=30)
            if download_result.returncode != 0:
                raise Exception(f"从 HDFS 下载 mapper 脚本失败: {download_result.stderr}")
            
            # 确保脚本有执行权限
            chmod_cmd = ["docker", "exec", "hadoop-namenode", "chmod", "+x", mapper_local]
            subprocess.run(chmod_cmd, capture_output=True, timeout=10)
            
            if reducer_local:
                download_cmd = ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-get", reducer_hdfs, reducer_local]
                download_result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=30)
                if download_result.returncode != 0:
                    raise Exception(f"从 HDFS 下载 reducer 脚本失败: {download_result.stderr}")
                
                # 确保脚本有执行权限
                chmod_cmd = ["docker", "exec", "hadoop-namenode", "chmod", "+x", reducer_local]
                subprocess.run(chmod_cmd, capture_output=True, timeout=10)
            
            # 构建命令
            # Hadoop Streaming 会将 -file 指定的文件分发到任务工作目录
            # 因此 mapper/reducer 命令中应使用文件名（不带路径）
            # 注意：NodeManager 使用 Python 3.9，路径为 /usr/local/bin/python3
            # 使用绝对路径确保能找到正确的 Python
            mapper_file = mapper_name
            reducer_file = reducer_name if reducer_name else None
            
            # 使用绝对路径的 Python 命令（NodeManager 容器中的 Python 3.9）
            # 这样可以确保即使 PATH 环境变量不正确也能找到 Python
            python_cmd = "/usr/local/bin/python3"
            
            cmd = [ "docker", "exec", "hadoop-namenode",
                "hadoop", "jar",
                self.streaming_jar,
                "-input", input_path,
                "-output", output_path,
                "-mapper", f"{python_cmd} {mapper_file}",
                "-file", mapper_local,
            ]
            
            if reducer_local and reducer_file:
                cmd.extend(["-reducer", f"{python_cmd} {reducer_file}", "-file", reducer_local])
            
            # 设置 Python 环境
            # 确保 PYTHONPATH 包含必要的路径
            # NodeManager 的 Python 3.9 安装在 /usr/local/lib/python3.9/site-packages
            # 设置 PATH 确保能找到 Python 和其他工具
            cmd.extend([
                "-cmdenv", f"PYTHONPATH={self.hadoop_home}:/usr/local/lib/python3.9/site-packages",
                "-cmdenv", "HADOOP_MAPRED_HOME=/opt/hadoop-3.2.1",
                "-cmdenv", "PATH=/usr/local/bin:/usr/bin:/bin",
            ])
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 提交任务
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            # 清理临时文件
            subprocess.run(
                ["docker", "exec", "hadoop-namenode", "rm", "-f", mapper_local],
                capture_output=True,
                timeout=10
            )
            if reducer_local:
                subprocess.run(
                    ["docker", "exec", "hadoop-namenode", "rm", "-f", reducer_local],
                    capture_output=True,
                    timeout=10
                )
            
            if result.returncode != 0:
                # 输出完整的错误信息
                error_msg = result.stderr or result.stdout
                logger.error(f"{job_name} 任务失败:")
                logger.error(f"返回码: {result.returncode}")
                logger.error(f"标准错误: {result.stderr}")
                logger.error(f"标准输出: {result.stdout}")
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
            script_path: 本地脚本路径（相对或绝对路径）
            
        Returns:
            HDFS 路径
        """
        # 转换为绝对路径
        original_script_path = script_path
        if not os.path.isabs(script_path):
            # 相对于项目根目录
            # __file__ 是 backend/hadoop_service.py，需要向上两级到项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(project_root, script_path)
        
        # 标准化路径（用于文件检查）
        script_path = os.path.normpath(script_path)
        
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"脚本文件不存在: {script_path} (原始路径: {original_script_path})")
        
        script_name = os.path.basename(script_path)
        hdfs_path = f"{self.hdfs_root}/scripts/{script_name}"
        
        # 确保 HDFS 目录存在
        subprocess.run(
            ["docker", "exec", "hadoop-namenode", "hadoop", "fs", "-mkdir", "-p", f"{self.hdfs_root}/scripts"],
            capture_output=True,
            timeout=30
        )
        
        # 先将脚本复制到容器内的临时目录
        container_temp_path = f"/tmp/{script_name}"
        copy_result = subprocess.run(
            ["docker", "cp", script_path, f"hadoop-namenode:{container_temp_path}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if copy_result.returncode != 0:
            raise Exception(f"复制脚本到容器失败: {copy_result.stderr}")
        
        # 从容器内的临时路径上传到 HDFS
        put_result = subprocess.run(
            [
                "docker", "exec", "hadoop-namenode",
                "hadoop", "fs", "-put", "-f", container_temp_path, hdfs_path
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # 清理容器内的临时文件
        subprocess.run(
            ["docker", "exec", "hadoop-namenode", "rm", "-f", container_temp_path],
            capture_output=True,
            timeout=10
        )
        
        if put_result.returncode != 0:
            raise Exception(f"HDFS 上传失败: {put_result.stderr}")
        
        logger.info(f"脚本已上传到 HDFS: {hdfs_path}")
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


