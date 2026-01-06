"""
Hadoop 工具函数
用于执行 MapReduce 任务和管理 Hadoop 作业
"""

import os
import subprocess
import logging
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class HadoopJobManager:
    """Hadoop 作业管理器"""
    
    def __init__(self, hadoop_home: Optional[str] = None):
        """
        初始化 Hadoop 作业管理器
        
        Args:
            hadoop_home: Hadoop 安装路径（如果不在 PATH 中）
        """
        self.hadoop_home = hadoop_home or os.getenv("HADOOP_HOME", "")
        self.hadoop_cmd = "hadoop"
        if self.hadoop_home:
            self.hadoop_cmd = f"{self.hadoop_home}/bin/hadoop"
    
    def run_mapreduce_job(
        self,
        input_path: str,
        output_path: str,
        mapper: str,
        reducer: Optional[str] = None,
        files: Optional[List[str]] = None,
        job_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        运行 MapReduce 作业
        
        Args:
            input_path: 输入路径（HDFS）
            output_path: 输出路径（HDFS）
            mapper: Mapper 脚本路径
            reducer: Reducer 脚本路径（可选）
            files: 附加文件列表（如依赖的 Python 脚本）
            job_name: 作业名称
            
        Returns:
            作业执行结果
        """
        try:
            # 构建 hadoop streaming 命令
            cmd = [
                self.hadoop_cmd,
                "jar",
                "share/hadoop/tools/lib/hadoop-streaming-*.jar",  # 需要替换为实际路径
                "-input", input_path,
                "-output", output_path,
                "-mapper", mapper,
            ]
            
            if reducer:
                cmd.extend(["-reducer", reducer])
            
            if files:
                for file in files:
                    cmd.extend(["-file", file])
            
            if job_name:
                cmd.extend(["-jobconf", f"mapreduce.job.name={job_name}"])
            
            # 执行命令
            logger.info(f"执行 MapReduce 作业: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("MapReduce 作业执行成功")
                return {
                    "success": True,
                    "output": result.stdout,
                    "output_path": output_path
                }
            else:
                logger.error(f"MapReduce 作业执行失败: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }
                
        except Exception as e:
            logger.error(f"执行 MapReduce 作业时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_job_status(self, job_id: str) -> Dict[str, any]:
        """
        检查作业状态
        
        Args:
            job_id: 作业 ID
            
        Returns:
            作业状态信息
        """
        try:
            cmd = [self.hadoop_cmd, "job", "-status", job_id]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "status": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
        except Exception as e:
            logger.error(f"检查作业状态时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def get_hadoop_streaming_jar() -> Optional[str]:
    """
    查找 Hadoop Streaming JAR 文件路径
    
    Returns:
        JAR 文件路径，如果找不到则返回 None
    """
    hadoop_home = os.getenv("HADOOP_HOME", "")
    
    if hadoop_home:
        jar_path = Path(hadoop_home) / "share" / "hadoop" / "tools" / "lib" / "hadoop-streaming-*.jar"
        # 尝试查找匹配的 JAR 文件
        import glob
        jars = glob.glob(str(jar_path))
        if jars:
            return jars[0]
    
    # 尝试在常见位置查找
    common_paths = [
        "/usr/lib/hadoop/share/hadoop/tools/lib/hadoop-streaming-*.jar",
        "/opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-*.jar",
    ]
    
    import glob
    for path_pattern in common_paths:
        jars = glob.glob(path_pattern)
        if jars:
            return jars[0]
    
    logger.warning("找不到 Hadoop Streaming JAR 文件")
    return None

