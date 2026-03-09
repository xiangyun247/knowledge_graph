#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一「提取后」文本清洗

供单文件上传、知识库入库、KG 构建等所有使用「提取正文」的链路复用。
与 hadoop/mapreduce/text_clean 的医学清洗逻辑保持一致，避免 backend 依赖 hadoop。
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 参考文献/致谢截断（匹配到即截断，后续行丢弃）
_CUTOFF_PATTERNS = [
    r"^\s*参考文献\s*$",
    r"^\s*参考资料\s*$",
    r"^\s*致谢\s*$",
    r"^\s*Acknowledg?ement[s]?\s*$",
    r"^\s*References\s*$",
    r"^\s*BIBLIOGRAPHY\s*$",
    r"^\s*Bibliography\s*$",
]
_CUTOFF_REGEX = re.compile("|".join(_CUTOFF_PATTERNS), re.IGNORECASE)

_MEDICAL_KEYWORDS = [
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
    "risk", "factor", "complication", "outcome", "prognosis",
]


def _looks_like_figure_or_table(line: str) -> bool:
    line_strip = line.strip()
    if re.match(r"^(图|表)\s*\d+", line_strip):
        return True
    if re.match(r"^(Figure|Fig\.?|Table|TAB\.)\s*\d+", line_strip, re.IGNORECASE):
        return True
    return False


def _is_mostly_numeric_or_garbage(line: str) -> bool:
    if len(line) < 6:
        return True
    chars = [c for c in line if not c.isspace()]
    if not chars:
        return True
    digits = sum(c.isdigit() for c in chars)
    punct = sum(c in ".,;:[]()%+-=<>/\\|~" for c in chars)
    ratio = (digits + punct) / max(len(chars), 1)
    return ratio > 0.6


def _contains_medical_keyword(line: str) -> bool:
    lower = line.lower()
    return any(k in line or k in lower for k in _MEDICAL_KEYWORDS)


def clean_medical_text(raw_text: Optional[str]) -> str:
    """
    针对医学论文/指南的正文进行清洗，供「提取后」统一使用。

    包含：统一换行、参考文献截断、页眉页脚/图表标题过滤、
    引用标记与 URL/邮箱去除、多空格压缩等。

    Args:
        raw_text: 原始提取文本（PDF/TXT 等）

    Returns:
        清洗后的文本
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    filtered_lines = []

    for line in lines:
        if _CUTOFF_REGEX.match(line):
            break
        line_strip = line.strip()
        if not line_strip:
            continue
        if re.search(r"Page\s+\d+\s+of\s+\d+", line_strip, re.IGNORECASE):
            continue
        if re.search(r"第\s*\d+\s*页", line_strip):
            continue
        if _looks_like_figure_or_table(line_strip):
            continue
        if _is_mostly_numeric_or_garbage(line_strip):
            continue
        if len(line_strip) < 15 and not _contains_medical_keyword(line_strip):
            continue
        filtered_lines.append(line_strip)

    cleaned_lines = []
    for line in filtered_lines:
        line = re.sub(r"\[[0-9,\-\s]+\]", "", line)
        line = re.sub(r"\([A-Z][A-Za-z].{0,40}?\d{4}\)", "", line)
        line = re.sub(r"http[s]?://\S+", "", line)
        line = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def normalize_control_chars(text: Optional[str]) -> str:
    """
    轻度规范化：去除控制字符、不可见字符，统一空白。
    适用于对「保留更多原文」的 KG 构建前处理。
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
