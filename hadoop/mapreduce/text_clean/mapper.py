#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本清洗 Mapper
用于 Hadoop MapReduce 任务

从 HDFS 读取提取的文本，进行医学文本清洗
输出格式：文件路径 \t 清洗后的文本
"""

import sys
import re
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_medical_text(raw_text: str) -> str:
    """
    针对医学论文 / 指南的文本进行清洗
    
    Args:
        raw_text: 原始文本
        
    Returns:
        清洗后的文本
    """
    if not raw_text:
        return ""
    
    # 统一换行符
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    
    # 1) 按参考文献/致谢截断
    cutoff_patterns = [
        r"^\s*参考文献\s*$",
        r"^\s*参考资料\s*$",
        r"^\s*致谢\s*$",
        r"^\s*Acknowledg?ement[s]?\s*$",
        r"^\s*References\s*$",
        r"^\s*BIBLIOGRAPHY\s*$",
        r"^\s*Bibliography\s*$",
    ]
    cutoff_regex = re.compile("|".join(cutoff_patterns), re.IGNORECASE)
    
    lines = text.split("\n")
    filtered_lines = []
    
    medical_keywords = [
        "炎", "癌", "综合征", "综合症", "症", "疾病", "病因", "病程", "病理", "病变",
        "诊断", "治疗", "用药", "药物", "方案", "疗法", "干预", "预后", "预防",
        "风险", "危险因素", "并发症", "感染", "出血", "坏死",
        "患者", "病人", "临床", "指南", "推荐", "随访", "复发",
        "胰腺", "胰腺炎", "胰腺癌", "肝", "肾", "心功能",
        "pancreatitis", "pancreas", "acute", "chronic",
        "disease", "syndrome", "disorder",
        "treatment", "therapy", "management",
        "diagnosis", "diagnostic",
        "clinical", "patient", "patients",
        "risk", "factor", "complication", "outcome", "prognosis"
    ]
    
    def looks_like_figure_or_table(line: str) -> bool:
        line_strip = line.strip()
        if re.match(r"^(图|表)\s*\d+", line_strip):
            return True
        if re.match(r"^(Figure|Fig\.?|Table|TAB\.)\s*\d+", line_strip, re.IGNORECASE):
            return True
        return False
    
    def is_mostly_numeric_or_garbage(line: str) -> bool:
        if len(line) < 6:
            return True
        chars = [c for c in line if not c.isspace()]
        if not chars:
            return True
        digits = sum(c.isdigit() for c in chars)
        punct = sum(c in ".,;:[]()%+-=<>/\\|~" for c in chars)
        ratio = (digits + punct) / max(len(chars), 1)
        return ratio > 0.6
    
    def contains_medical_keyword(line: str) -> bool:
        lower = line.lower()
        return any(k in line or k in lower for k in medical_keywords)
    
    # 2) 逐行处理 + 截断参考文献
    for line in lines:
        # 截断逻辑
        if cutoff_regex.match(line):
            break
        
        line_strip = line.strip()
        if not line_strip:
            continue
        
        # 页眉页脚过滤
        if re.search(r"Page\s+\d+\s+of\s+\d+", line_strip, re.IGNORECASE):
            continue
        if re.search(r"第\s*\d+\s*页", line_strip):
            continue
        
        # 图表标题
        if looks_like_figure_or_table(line_strip):
            continue
        
        # 纯数字/符号
        if is_mostly_numeric_or_garbage(line_strip):
            continue
        
        # 很短且不含医学关键词
        if len(line_strip) < 15 and not contains_medical_keyword(line_strip):
            continue
        
        filtered_lines.append(line_strip)
    
    # 3) 行内清洗
    cleaned_lines = []
    for line in filtered_lines:
        # 删掉引用标记 [1] [2-5]
        line = re.sub(r"\[[0-9,\-\s]+\]", "", line)
        
        # 删除文献引用 (Smith 2020)
        line = re.sub(r"\([A-Z][A-Za-z].{0,40}?\d{4}\)", "", line)
        
        # 去掉 URL
        line = re.sub(r"http[s]?://\S+", "", line)
        
        # 去掉邮箱
        line = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", line)
        
        # 多空格压缩
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    
    cleaned_text = "\n".join(cleaned_lines)
    return cleaned_text


def mapper():
    """
    Mapper 函数
    从标准输入读取文本，清洗后输出
    """
    try:
        # 从标准输入读取数据（格式：文件路径 \t 文本内容）
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            # 分割文件路径和文本内容
            parts = line.split('\t', 1)
            if len(parts) < 2:
                logger.warning("输入格式错误，跳过: {}".format(line))
                continue
            
            file_path = parts[0]
            raw_text = parts[1]
            
            logger.info("清洗文本: {}".format(file_path))
            
            # 清洗文本
            cleaned_text = clean_medical_text(raw_text)
            
            # 输出：文件路径 \t 清洗后的文本
            output = "{}\t{}".format(file_path, cleaned_text)
            print(output)
            
    except Exception as e:
        logger.error("Mapper 执行出错: {}".format(e))
        sys.stderr.write("ERROR: {}\n".format(e))
        sys.exit(1)


if __name__ == "__main__":
    mapper()


