"""
HDFS 客户端封装
用于与 Hadoop HDFS 交互
"""

import os
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from hdfs3 import HDFileSystem
    HDFS3_AVAILABLE = True
except ImportError:
    HDFS3_AVAILABLE = False
    logger.warning("hdfs3 未安装，HDFS 功能将不可用")

try:
    import subprocess
    SUBPROCESS_AVAILABLE = True
except ImportError:
    SUBPROCESS_AVAILABLE = False


class HDFSClient:
    """HDFS 客户端封装类"""
    
    def __init__(self, host: str = "localhost", port: int = 8020, use_docker: bool = True):
        """
        初始化 HDFS 客户端
        
        Args:
            host: HDFS NameNode 主机地址
            port: HDFS 端口（默认 8020，Hadoop 3.x 默认 RPC 端口）
            use_docker: 是否使用 Docker 方式访问（默认 True，适合容器化环境）
        """
        self.host = host
        self.port = port
        self.use_docker = use_docker
        self.hdfs = None
        self.container_name = "hadoop-namenode"  # Docker 容器名称
        
        # 在 Docker 环境下，优先使用 docker exec 方式
        if use_docker:
            # 检查容器是否存在
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if self.container_name in result.stdout:
                    logger.info(f"HDFS 客户端使用 Docker 方式: {self.container_name}")
                    return
                else:
                    logger.warning(f"Docker 容器 {self.container_name} 未运行，尝试其他方式")
            except Exception as e:
                logger.warning(f"检查 Docker 容器失败: {e}，尝试其他方式")
        
        # 非 Docker 环境或 Docker 不可用时，尝试 hdfs3 库
        if HDFS3_AVAILABLE:
            try:
                self.hdfs = HDFileSystem(host=host, port=port)
                logger.info(f"HDFS 客户端初始化成功 (hdfs3): {host}:{port}")
            except Exception as e:
                logger.error(f"HDFS 客户端初始化失败: {e}")
                self.hdfs = None
        else:
            logger.warning("hdfs3 未安装，将使用命令行方式访问 HDFS")
    
    def upload_file(self, local_path: str, hdfs_path: str) -> bool:
        """
        上传文件到 HDFS
        
        Args:
            local_path: 本地文件路径
            hdfs_path: HDFS 文件路径
            
        Returns:
            是否成功
        """
        try:
            if self.use_docker and self.container_name:
                # 使用 Docker 方式：先将文件复制到容器，再上传
                import tempfile
                import os
                
                # 先复制到容器临时目录
                container_temp = f"/tmp/{os.path.basename(local_path)}"
                copy_result = subprocess.run(
                    ["docker", "cp", local_path, f"{self.container_name}:{container_temp}"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if copy_result.returncode != 0:
                    logger.error(f"复制文件到容器失败: {copy_result.stderr}")
                    return False
                
                # 从容器内上传到 HDFS
                cmd = [
                    "docker", "exec", self.container_name,
                    "hadoop", "fs", "-put", "-f", container_temp, hdfs_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                # 清理临时文件
                subprocess.run(
                    ["docker", "exec", self.container_name, "rm", "-f", container_temp],
                    capture_output=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info(f"文件上传成功: {local_path} -> {hdfs_path}")
                    return True
                else:
                    logger.error(f"文件上传失败: {result.stderr}")
                    return False
            elif self.hdfs:
                # 使用 hdfs3 库
                self.hdfs.put(local_path, hdfs_path)
                logger.info(f"文件上传成功: {local_path} -> {hdfs_path}")
                return True
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -put {local_path} {hdfs_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"文件上传成功: {local_path} -> {hdfs_path}")
                    return True
                else:
                    logger.error(f"文件上传失败: {result.stderr}")
                    return False
        except Exception as e:
            logger.error(f"上传文件时出错: {e}")
            return False
    
    def download_file(self, hdfs_path: str, local_path: str) -> bool:
        """
        从 HDFS 下载文件
        
        Args:
            hdfs_path: HDFS 文件路径
            local_path: 本地文件路径
            
        Returns:
            是否成功
        """
        try:
            if self.hdfs:
                # 使用 hdfs3 库
                self.hdfs.get(hdfs_path, local_path)
                logger.info(f"文件下载成功: {hdfs_path} -> {local_path}")
                return True
            elif self.use_docker and self.container_name:
                # 使用 Docker 方式：先下载到容器临时目录，再复制出来
                import tempfile
                import os
                
                container_temp = f"/tmp/{os.path.basename(local_path)}"
                cmd = [
                    "docker", "exec", self.container_name,
                    "hadoop", "fs", "-get", hdfs_path, container_temp
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # 从容器复制到本地
                    copy_result = subprocess.run(
                        ["docker", "cp", f"{self.container_name}:{container_temp}", local_path],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    # 清理容器临时文件
                    subprocess.run(
                        ["docker", "exec", self.container_name, "rm", "-f", container_temp],
                        capture_output=True,
                        timeout=10
                    )
                    
                    if copy_result.returncode == 0:
                        logger.info(f"文件下载成功: {hdfs_path} -> {local_path}")
                        return True
                    else:
                        logger.error(f"从容器复制文件失败: {copy_result.stderr}")
                        return False
                else:
                    logger.error(f"文件下载失败: {result.stderr}")
                    return False
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -get {hdfs_path} {local_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"文件下载成功: {hdfs_path} -> {local_path}")
                    return True
                else:
                    logger.error(f"文件下载失败: {result.stderr}")
                    return False
        except Exception as e:
            logger.error(f"下载文件时出错: {e}")
            return False
    
    def list_files(self, hdfs_path: str) -> List[str]:
        """
        列出 HDFS 目录中的文件
        
        Args:
            hdfs_path: HDFS 目录路径
            
        Returns:
            文件列表
        """
        try:
            if self.hdfs:
                # 使用 hdfs3 库
                files = self.hdfs.ls(hdfs_path)
                return [f for f in files if not f.endswith('/')]
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -ls {hdfs_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    # 解析输出
                    lines = result.stdout.strip().split('\n')
                    files = []
                    for line in lines[1:]:  # 跳过第一行（总计信息）
                        parts = line.split()
                        if len(parts) >= 8:
                            files.append(parts[-1])
                    return files
                else:
                    logger.error(f"列出文件失败: {result.stderr}")
                    return []
        except Exception as e:
            logger.error(f"列出文件时出错: {e}")
            return []
    
    def delete_file(self, hdfs_path: str) -> bool:
        """
        删除 HDFS 文件
        
        Args:
            hdfs_path: HDFS 文件路径
            
        Returns:
            是否成功
        """
        try:
            if self.hdfs:
                # 使用 hdfs3 库
                self.hdfs.rm(hdfs_path)
                logger.info(f"文件删除成功: {hdfs_path}")
                return True
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -rm {hdfs_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"文件删除成功: {hdfs_path}")
                    return True
                else:
                    logger.error(f"文件删除失败: {result.stderr}")
                    return False
        except Exception as e:
            logger.error(f"删除文件时出错: {e}")
            return False
    
    def exists(self, hdfs_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            hdfs_path: HDFS 文件路径
            
        Returns:
            是否存在
        """
        try:
            if self.hdfs:
                # 使用 hdfs3 库
                return self.hdfs.exists(hdfs_path)
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -test -e {hdfs_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.returncode == 0
        except Exception as e:
            logger.error(f"检查文件存在性时出错: {e}")
            return False
    
    def mkdir(self, hdfs_path: str) -> bool:
        """
        创建 HDFS 目录
        
        Args:
            hdfs_path: HDFS 目录路径
            
        Returns:
            是否成功
        """
        try:
            if self.hdfs:
                # 使用 hdfs3 库
                self.hdfs.mkdir(hdfs_path)
                logger.info(f"目录创建成功: {hdfs_path}")
                return True
            else:
                # 使用命令行方式
                cmd = f"hdfs dfs -mkdir -p {hdfs_path}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"目录创建成功: {hdfs_path}")
                    return True
                else:
                    logger.error(f"目录创建失败: {result.stderr}")
                    return False
        except Exception as e:
            logger.error(f"创建目录时出错: {e}")
            return False
    
    def close(self):
        """关闭 HDFS 连接"""
        if self.hdfs:
            try:
                self.hdfs.disconnect()
                logger.info("HDFS 连接已关闭")
            except Exception as e:
                logger.error(f"关闭 HDFS 连接时出错: {e}")


