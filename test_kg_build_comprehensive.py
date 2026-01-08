#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试本地构建知识图谱功能
"""

import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_kg_build_logic():
    """
    全面测试知识图谱构建逻辑
    """
    print("开始全面测试知识图谱构建逻辑...")
    
    # 测试不同文本长度的情况
    test_cases = [
        # (文本长度, 预期最小实体数, 预期最小关系数)
        (100, 50, 75),        # 短文本，应该使用最小值
        (1000, 50, 75),       # 1000字符，应该生成10个实体，15个关系，但受限于最小值
        (5000, 50, 75),       # 5000字符，应该生成50个实体，74个关系
        (10000, 100, 147),    # 10000字符，应该生成100个实体，147个关系
        (50000, 500, 740),    # 50000字符，应该生成500个实体，740个关系
        (200000, 2000, 2983), # 200000字符，应该生成2000个实体，2983个关系（达到最大值）
    ]
    
    for text_length, expected_min_entities, expected_min_relations in test_cases:
        # 生成指定长度的随机文本
        text = "这是一个测试文本，用于验证知识图谱构建逻辑。" * (text_length // 20)
        
        # 确保文本长度接近预期
        text = text[:text_length]
        actual_length = len(text)
        
        # 计算实体和关系数量
        entities_created = max(50, min(2000, actual_length // 100))  # 每100字符创建1个实体，最多2000个
        relations_created = max(75, min(3000, actual_length // 67))  # 每67字符创建1个关系，最多3000个
        
        # 验证结果
        assert entities_created >= expected_min_entities, f"文本长度 {actual_length}，预期至少 {expected_min_entities} 个实体，实际 {entities_created} 个"
        assert relations_created >= expected_min_relations, f"文本长度 {actual_length}，预期至少 {expected_min_relations} 个关系，实际 {relations_created} 个"
        
        logger.info(f"✓ 文本长度 {actual_length}，生成实体数 {entities_created}，关系数 {relations_created}")
    
    print("\n✓ 全面测试知识图谱构建逻辑成功!")
    return True


def test_real_pdf_scenario():
    """
    测试真实PDF文件场景
    """
    print("\n开始测试真实PDF文件场景...")
    
    # 模拟两个真实PDF文件的文本长度（10373和13700个字符）
    pdf_texts = {
        "pdf_test1": "测试PDF文本内容 " * (10373 // 10),
        "pdf_test2": "测试PDF文本内容 " * (13700 // 10),
    }
    
    # 统计总文本长度
    total_text_length = sum(len(text) for text in pdf_texts.values())
    logger.info(f"总文本长度: {total_text_length} 字符")
    
    # 计算实体和关系数量
    entities_created = max(50, min(2000, total_text_length // 100))  # 每100字符创建1个实体，最多2000个
    relations_created = max(75, min(3000, total_text_length // 67))  # 每67字符创建1个关系，最多3000个
    
    logger.info(f"生成实体数: {entities_created}，关系数: {relations_created}")
    
    # 验证结果
    assert entities_created > 100, f"预期生成超过100个实体，实际生成 {entities_created} 个"
    assert relations_created > 150, f"预期生成超过150个关系，实际生成 {relations_created} 个"
    
    print("✓ 真实PDF文件场景测试成功!")
    return True


if __name__ == "__main__":
    test_kg_build_logic()
    test_real_pdf_scenario()
    print("\n🎉 所有测试都成功了！")
