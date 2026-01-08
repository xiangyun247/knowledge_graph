#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面的 Mapper 脚本测试工具

功能：
1. 检查所有 mapper 脚本的语法
2. 检查依赖是否安装
3. 测试 mapper 脚本的基本功能
4. 测试实际的 Hadoop Streaming 任务
5. 提供详细的错误诊断
"""

import os
import sys
import subprocess
import tempfile
import json
from typing import Dict, List, Tuple, Any

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mapper 脚本路径
MAPPER_SCRIPTS = {
    "pdf_extract": {
        "mapper": "hadoop/mapreduce/pdf_extract/mapper.py",
        "reducer": "hadoop/mapreduce/pdf_extract/reducer.py",
        "dependencies": ["pdfplumber"],
        "description": "PDF 文本提取"
    },
    "text_clean": {
        "mapper": "hadoop/mapreduce/text_clean/mapper.py",
        "reducer": None,
        "dependencies": [],
        "description": "文本清洗"
    },
    "text_chunk": {
        "mapper": "hadoop/mapreduce/text_chunk/mapper.py",
        "reducer": None,
        "dependencies": [],
        "description": "文本分块"
    }
}

# 容器名称
CONTAINER_NAME = "hadoop-nodemanager"


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_success(msg: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def print_error(msg: str):
    """打印错误消息"""
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def print_warning(msg: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def print_info(msg: str):
    """打印信息消息"""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def check_docker_container() -> bool:
    """检查 Docker 容器是否运行"""
    print("\n" + "=" * 60)
    print("1. 检查 Docker 容器")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if CONTAINER_NAME in result.stdout:
            print_success(f"容器 {CONTAINER_NAME} 正在运行")
            return True
        else:
            print_error(f"容器 {CONTAINER_NAME} 未运行")
            print_info("请先启动 Hadoop 容器: docker-compose up -d")
            return False
    except FileNotFoundError:
        print_error("Docker 未安装或不在 PATH 中")
        return False
    except Exception as e:
        print_error(f"检查容器失败: {e}")
        return False


def check_script_exists(script_path: str) -> bool:
    """检查脚本文件是否存在"""
    full_path = os.path.join(PROJECT_ROOT, script_path)
    if os.path.exists(full_path):
        return True
    return False


def check_script_syntax(script_path: str) -> Tuple[bool, str]:
    """检查脚本语法"""
    full_path = os.path.join(PROJECT_ROOT, script_path)
    
    # 复制到容器
    container_path = f"/tmp/{os.path.basename(script_path)}"
    copy_result = subprocess.run(
        ["docker", "cp", full_path, f"{CONTAINER_NAME}:{container_path}"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if copy_result.returncode != 0:
        return False, f"复制脚本失败: {copy_result.stderr}"
    
    # 检查语法
    syntax_result = subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "python3", "-m", "py_compile", container_path],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # 清理
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "rm", "-f", container_path],
        capture_output=True,
        timeout=10
    )
    
    if syntax_result.returncode == 0:
        return True, ""
    else:
        return False, syntax_result.stderr


def check_dependencies(script_name: str, dependencies: List[str]) -> Tuple[bool, List[str]]:
    """检查依赖是否安装"""
    missing = []
    
    for dep in dependencies:
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "python3", "-c", f"import {dep}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            missing.append(dep)
    
    return len(missing) == 0, missing


def test_mapper_basic(script_path: str, test_input: str = None) -> Tuple[bool, str, str]:
    """测试 mapper 脚本的基本功能"""
    full_path = os.path.join(PROJECT_ROOT, script_path)
    script_name = os.path.basename(script_path)
    container_path = f"/tmp/{script_name}"
    
    # 复制到容器
    copy_result = subprocess.run(
        ["docker", "cp", full_path, f"{CONTAINER_NAME}:{container_path}"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if copy_result.returncode != 0:
        return False, "", f"复制脚本失败: {copy_result.stderr}"
    
    # 设置可执行权限
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "chmod", "+x", container_path],
        capture_output=True,
        timeout=10
    )
    
    # 执行测试
    test_input_data = test_input if test_input else None
    result = subprocess.run(
        ["docker", "exec", "-i", CONTAINER_NAME, "python3", container_path],
        input=test_input_data,
        capture_output=True,
        text=True,
        timeout=60,
        encoding='utf-8',
        errors='ignore'
    )
    
    # 清理
    subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "rm", "-f", container_path],
        capture_output=True,
        timeout=10
    )
    
    success = result.returncode == 0
    return success, result.stdout, result.stderr


def test_text_clean_mapper() -> Tuple[bool, str]:
    """测试文本清洗 mapper"""
    print("\n测试文本清洗 mapper...")
    
    # 创建测试输入（使用包含医学关键词的文本，确保不会被过滤）
    test_input = "/test/file1.pdf\t患者出现急性胰腺炎症状，需要立即进行诊断和治疗。医生建议使用药物治疗方案。\n/test/file2.pdf\t慢性疾病患者需要长期随访，预防并发症的发生。临床指南推荐定期检查。"
    
    success, stdout, stderr = test_mapper_basic(
        MAPPER_SCRIPTS["text_clean"]["mapper"],
        test_input
    )
    
    if success:
        # 检查输出格式
        lines = [line for line in stdout.strip().split('\n') if line.strip()]
        if len(lines) >= 2:
            for line in lines:
                if '\t' not in line:
                    return False, f"输出格式错误: 缺少制表符分隔符\n输出: {stdout[:200]}"
                # 检查是否有文本内容（制表符后应该有内容）
                parts = line.split('\t', 1)
                if len(parts) < 2 or not parts[1].strip():
                    return False, f"输出内容为空: {line}\n完整输出: {stdout[:200]}"
            return True, "文本清洗 mapper 测试通过"
        else:
            return False, f"输出行数不足: 期望至少2行，实际{len(lines)}行\n输出: {stdout[:200]}"
    else:
        return False, f"执行失败: {stderr[:500]}"


def test_text_chunk_mapper() -> Tuple[bool, str]:
    """测试文本分块 mapper"""
    print("\n测试文本分块 mapper...")
    
    # 创建测试输入（长文本）
    long_text = " ".join(["测试文本"] * 200)  # 创建足够长的文本
    test_input = f"/test/file1.pdf\t{long_text}\n"
    
    success, stdout, stderr = test_mapper_basic(
        MAPPER_SCRIPTS["text_chunk"]["mapper"],
        test_input
    )
    
    if success:
        # 检查输出格式
        lines = stdout.strip().split('\n')
        if len(lines) > 0:
            for line in lines:
                if '\t' not in line:
                    return False, f"输出格式错误: 缺少制表符分隔符\n输出: {stdout[:200]}"
            return True, f"文本分块 mapper 测试通过，生成了 {len(lines)} 个块"
        else:
            return False, "没有输出"
    else:
        return False, f"执行失败: {stderr[:500]}"


def test_pdf_extract_mapper() -> Tuple[bool, str]:
    """测试 PDF 提取 mapper（需要真实的 PDF 文件）"""
    print("\n测试 PDF 提取 mapper...")
    
    # 检查是否有测试 PDF 文件
    test_pdf_path = "/knowledge_graph/uploads/test/test.pdf"
    
    # 检查文件是否存在
    check_result = subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "hadoop", "fs", "-test", "-e", test_pdf_path],
        capture_output=True,
        timeout=10
    )
    
    if check_result.returncode != 0:
        return False, f"测试 PDF 文件不存在: {test_pdf_path}\n请先上传一个 PDF 文件到 HDFS"
    
    # 使用真实的 PDF 路径测试
    test_input = f"{test_pdf_path}\n"
    
    success, stdout, stderr = test_mapper_basic(
        MAPPER_SCRIPTS["pdf_extract"]["mapper"],
        test_input
    )
    
    if success:
        # 检查输出格式
        if '\t' in stdout:
            return True, "PDF 提取 mapper 测试通过"
        else:
            return False, f"输出格式错误: 缺少制表符分隔符\n输出: {stdout[:200]}"
    else:
        # 检查是否是文件不存在错误
        if "No such file" in stderr or "ERROR:" in stdout:
            return False, f"PDF 文件处理失败: {stderr[:500]}\n这可能是正常的，如果 PDF 文件损坏或格式不支持"
        return False, f"执行失败: {stderr[:500]}"


def run_comprehensive_test() -> Dict[str, Any]:
    """运行全面测试"""
    results = {
        "container_check": False,
        "scripts": {}
    }
    
    # 1. 检查容器
    results["container_check"] = check_docker_container()
    if not results["container_check"]:
        return results
    
    # 2. 测试每个 mapper 脚本
    print("\n" + "=" * 60)
    print("2. 测试 Mapper 脚本")
    print("=" * 60)
    
    for script_name, script_info in MAPPER_SCRIPTS.items():
        print(f"\n{'='*60}")
        print(f"测试: {script_info['description']} ({script_name})")
        print(f"{'='*60}")
        
        script_result = {
            "exists": False,
            "syntax_ok": False,
            "dependencies_ok": False,
            "test_ok": False,
            "errors": []
        }
        
        # 检查文件是否存在
        mapper_path = script_info["mapper"]
        if check_script_exists(mapper_path):
            print_success(f"Mapper 脚本存在: {mapper_path}")
            script_result["exists"] = True
        else:
            print_error(f"Mapper 脚本不存在: {mapper_path}")
            script_result["errors"].append(f"脚本文件不存在: {mapper_path}")
            results["scripts"][script_name] = script_result
            continue
        
        # 检查 reducer（如果有）
        if script_info["reducer"]:
            reducer_path = script_info["reducer"]
            if check_script_exists(reducer_path):
                print_success(f"Reducer 脚本存在: {reducer_path}")
            else:
                print_error(f"Reducer 脚本不存在: {reducer_path}")
                script_result["errors"].append(f"Reducer 脚本不存在: {reducer_path}")
        
        # 检查语法
        print(f"\n检查语法: {mapper_path}")
        syntax_ok, syntax_error = check_script_syntax(mapper_path)
        if syntax_ok:
            print_success("语法检查通过")
            script_result["syntax_ok"] = True
        else:
            print_error(f"语法错误: {syntax_error}")
            script_result["errors"].append(f"语法错误: {syntax_error}")
        
        # 检查依赖
        if script_info["dependencies"]:
            print(f"\n检查依赖: {', '.join(script_info['dependencies'])}")
            deps_ok, missing = check_dependencies(script_name, script_info["dependencies"])
            if deps_ok:
                print_success("所有依赖已安装")
                script_result["dependencies_ok"] = True
            else:
                print_error(f"缺少依赖: {', '.join(missing)}")
                script_result["errors"].append(f"缺少依赖: {', '.join(missing)}")
                print_info(f"安装命令: docker exec {CONTAINER_NAME} pip install {' '.join(missing)}")
        else:
            script_result["dependencies_ok"] = True
        
        # 功能测试
        print(f"\n功能测试: {mapper_path}")
        if script_name == "text_clean":
            test_ok, test_msg = test_text_clean_mapper()
        elif script_name == "text_chunk":
            test_ok, test_msg = test_text_chunk_mapper()
        elif script_name == "pdf_extract":
            test_ok, test_msg = test_pdf_extract_mapper()
        else:
            test_ok, test_msg = False, "未知的脚本类型"
        
        if test_ok:
            print_success(test_msg)
            script_result["test_ok"] = True
        else:
            print_warning(test_msg)
            script_result["errors"].append(test_msg)
        
        results["scripts"][script_name] = script_result
    
    return results


def print_summary(results: Dict[str, Any]):
    """打印测试总结"""
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if not results["container_check"]:
        print_error("Docker 容器未运行，无法完成测试")
        return
    
    all_passed = True
    for script_name, script_result in results["scripts"].items():
        print(f"\n{script_name}:")
        if script_result["exists"] and script_result["syntax_ok"] and \
           script_result["dependencies_ok"] and script_result["test_ok"]:
            print_success("所有测试通过")
        else:
            all_passed = False
            if script_result["errors"]:
                for error in script_result["errors"]:
                    print_error(error)
    
    print("\n" + "=" * 60)
    if all_passed:
        print_success("所有 mapper 脚本测试通过！")
    else:
        print_warning("部分测试未通过，请查看上面的错误信息")
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("Mapper 脚本全面测试工具")
    print("=" * 60)
    
    results = run_comprehensive_test()
    print_summary(results)
    
    # 保存结果到文件
    output_file = os.path.join(PROJECT_ROOT, "mapper_test_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print_info(f"测试结果已保存到: {output_file}")
    
    # 返回退出码
    all_passed = results.get("container_check", False) and all(
        script_result.get("exists", False) and
        script_result.get("syntax_ok", False) and
        script_result.get("dependencies_ok", False) and
        script_result.get("test_ok", False)
        for script_result in results.get("scripts", {}).values()
    )
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

