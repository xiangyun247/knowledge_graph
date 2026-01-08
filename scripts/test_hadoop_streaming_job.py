#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试实际的 Hadoop Streaming 任务

这个脚本会：
1. 创建测试数据
2. 上传到 HDFS
3. 提交 Hadoop Streaming 任务
4. 检查输出结果
"""

import os
import sys
import subprocess
import tempfile
import time
from typing import Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTAINER_NAME = "hadoop-namenode"
HDFS_ROOT = "/knowledge_graph"


def print_step(msg: str):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"{msg}")
    print(f"{'='*60}")


def run_docker_cmd(cmd: list, timeout: int = 30) -> tuple:
    """运行 Docker 命令"""
    full_cmd = ["docker", "exec", CONTAINER_NAME] + cmd
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding='utf-8',
        errors='ignore'
    )
    return result.returncode == 0, result.stdout, result.stderr


def create_test_data() -> str:
    """创建测试数据文件"""
    print_step("1. 创建测试数据")
    
    # 创建包含医学文本的测试数据
    test_data = """这是测试文件1.pdf\t患者出现急性胰腺炎症状，需要立即进行诊断和治疗。医生建议使用药物治疗方案。临床指南推荐定期随访，预防并发症的发生。
这是测试文件2.pdf\t慢性疾病患者需要长期随访，预防并发症的发生。临床指南推荐定期检查。医生会根据患者的具体情况制定个性化的治疗方案。"""
    
    # 保存到临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
        f.write(test_data)
        temp_path = f.name
    
    print(f"测试数据已创建: {temp_path}")
    return temp_path


def upload_to_hdfs(local_path: str, hdfs_path: str) -> bool:
    """上传文件到 HDFS"""
    print_step(f"2. 上传文件到 HDFS: {hdfs_path}")
    
    # 先复制到容器
    container_temp = f"/tmp/{os.path.basename(local_path)}"
    copy_result = subprocess.run(
        ["docker", "cp", local_path, f"{CONTAINER_NAME}:{container_temp}"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if copy_result.returncode != 0:
        print(f"复制文件到容器失败: {copy_result.stderr}")
        return False
    
    # 确保目录存在
    dir_path = os.path.dirname(hdfs_path)
    success, _, _ = run_docker_cmd(["hadoop", "fs", "-mkdir", "-p", dir_path])
    
    # 上传到 HDFS
    success, stdout, stderr = run_docker_cmd(
        ["hadoop", "fs", "-put", "-f", container_temp, hdfs_path]
    )
    
    # 清理容器内临时文件
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "rm", "-f", container_temp],
        capture_output=True,
        timeout=10
    )
    
    if success:
        print(f"文件已上传: {hdfs_path}")
        return True
    else:
        print(f"上传失败: {stderr}")
        return False


def test_text_clean_job() -> Dict[str, Any]:
    """测试文本清洗任务"""
    print_step("测试文本清洗 Hadoop Streaming 任务")
    
    result = {
        "success": False,
        "error": None,
        "output": None
    }
    
    try:
        # 1. 创建测试数据
        test_file = create_test_data()
        input_hdfs = f"{HDFS_ROOT}/test/input/text_clean_{int(time.time())}.txt"
        
        try:
            # 2. 上传测试数据
            if not upload_to_hdfs(test_file, input_hdfs):
                result["error"] = "上传测试数据失败"
                return result
            
            # 3. 上传 mapper 脚本
            mapper_local = os.path.join(PROJECT_ROOT, "hadoop/mapreduce/text_clean/mapper.py")
            mapper_hdfs = f"{HDFS_ROOT}/scripts/text_clean_mapper.py"
            if not upload_to_hdfs(mapper_local, mapper_hdfs):
                result["error"] = "上传 mapper 脚本失败"
                return result
            
            # 4. 准备输出路径
            output_hdfs = f"{HDFS_ROOT}/test/output/text_clean_{int(time.time())}"
            
            # 5. 下载脚本到容器本地（Hadoop Streaming 需要）
            mapper_name = "text_clean_mapper.py"
            mapper_local_container = f"/tmp/{mapper_name}"
            success, _, stderr = run_docker_cmd(
                ["hadoop", "fs", "-get", mapper_hdfs, mapper_local_container]
            )
            if not success:
                result["error"] = f"下载脚本失败: {stderr}"
                return result
            
            # 6. 设置可执行权限
            run_docker_cmd(["chmod", "+x", mapper_local_container])
            
            # 7. 提交 Hadoop Streaming 任务
            print_step("3. 提交 Hadoop Streaming 任务")
            
            streaming_jar = "/opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar"
            
            cmd = [
                "hadoop", "jar", streaming_jar,
                "-input", input_hdfs,
                "-output", output_hdfs,
                "-mapper", f"python3 {mapper_name}",
                "-file", mapper_local_container,
                "-cmdenv", "PYTHONPATH=/opt/hadoop-3.2.1",
            ]
            
            print(f"执行命令: {' '.join(cmd)}")
            success, stdout, stderr = run_docker_cmd(cmd, timeout=300)
            
            # 清理
            run_docker_cmd(["rm", "-f", mapper_local_container])
            
            if not success:
                result["error"] = f"任务执行失败:\n标准输出: {stdout}\n标准错误: {stderr}"
                return result
            
            # 8. 检查输出
            print_step("4. 检查输出结果")
            success, stdout, stderr = run_docker_cmd(
                ["hadoop", "fs", "-ls", output_hdfs]
            )
            
            if success:
                print("输出目录内容:")
                print(stdout)
                
                # 读取输出文件
                success, stdout, stderr = run_docker_cmd(
                    ["hadoop", "fs", "-cat", f"{output_hdfs}/part-00000"]
                )
                
                if success:
                    print("\n输出内容:")
                    print(stdout)
                    result["output"] = stdout
                    result["success"] = True
                else:
                    # 尝试使用 -text 选项
                    success2, stdout2, stderr2 = run_docker_cmd(
                        ["hadoop", "fs", "-text", f"{output_hdfs}/part-00000"]
                    )
                    if success2:
                        print("\n输出内容 (使用 -text):")
                        print(stdout2)
                        result["output"] = stdout2
                        result["success"] = True
                    else:
                        result["error"] = f"读取输出文件失败: {stderr} (尝试 -text 也失败: {stderr2})"
            else:
                result["error"] = f"列出输出目录失败: {stderr}"
            
        finally:
            # 清理本地临时文件
            if os.path.exists(test_file):
                os.unlink(test_file)
        
    except Exception as e:
        result["error"] = f"异常: {str(e)}"
        import traceback
        traceback.print_exc()
    
    return result


def main():
    """主函数"""
    print("=" * 60)
    print("Hadoop Streaming 任务测试")
    print("=" * 60)
    
    # 检查容器
    print("\n检查容器状态...")
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if CONTAINER_NAME not in result.stdout:
        print(f"错误: 容器 {CONTAINER_NAME} 未运行")
        print("请先启动 Hadoop 容器: docker-compose up -d")
        sys.exit(1)
    
    print(f"容器 {CONTAINER_NAME} 正在运行")
    
    # 测试文本清洗任务
    result = test_text_clean_job()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    
    if result["success"]:
        print("[OK] 测试通过")
        if result["output"]:
            print("\n输出内容预览:")
            print(result["output"][:500])
    else:
        print("[FAIL] 测试失败")
        if result["error"]:
            print(f"\n错误信息:\n{result['error']}")
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

