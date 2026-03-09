#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 增强提取：正文 + 表格 + 扫描页 OCR
- 表格：pdfplumber extract_tables() 转成文本参与构建/检索
- 扫描版：每页正文过短时用 PaddleOCR（页图由 PyMuPDF 渲染）补全，再统一走清洗
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# 可选配置（环境变量）
PDF_EXTRACT_ENABLE_OCR = os.getenv("PDF_EXTRACT_ENABLE_OCR", "1").strip().lower() in ("1", "true", "yes")
PDF_EXTRACT_MIN_TEXT_PER_PAGE = int(os.getenv("PDF_EXTRACT_MIN_TEXT_PER_PAGE", "50"))


def _tables_to_text(tables: List[List[List[Optional[str]]]]) -> str:
    """将 pdfplumber 的 extract_tables() 结果转为可读文本（Markdown 表风格）。"""
    if not tables:
        return ""
    lines = []
    for ti, table in enumerate(tables):
        if not table:
            continue
        # 每行用 | 连接单元格，空单元格用空格占位
        for row in table:
            cells = [str(c).strip() if c is not None else "" for c in row]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")  # 表后空行
    return "\n".join(lines).strip()


def _page_text_and_tables(page) -> str:
    """单页：正文 + 表格文本。"""
    text = (page.extract_text() or "").strip()
    tables = []
    try:
        tables = page.extract_tables() or []
    except Exception as e:
        logger.debug("extract_tables 失败: %s", e)
    table_text = _tables_to_text(tables)
    if table_text:
        text = (text + "\n\n[表]\n" + table_text).strip()
    return text or ""


def _render_page_to_png_bytes(pdf_path: str, page_index: int, dpi: int = 150) -> Optional[bytes]:
    """用 PyMuPDF 将 PDF 指定页渲染为 PNG 字节。"""
    try:
        import pymupdf
    except ImportError:
        logger.debug("pymupdf 未安装，无法渲染 PDF 页为图像")
        return None
    try:
        doc = pymupdf.open(pdf_path)
        try:
            if page_index >= len(doc):
                return None
            page = doc[page_index]
            zoom = dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            return pix.tobytes("png")
        finally:
            doc.close()
    except Exception as e:
        logger.warning("PDF 页渲染失败 path=%s page=%s: %s", pdf_path, page_index, e)
        return None


def _ocr_page_image(image_bytes: bytes) -> str:
    """对单张页图做 OCR，返回识别文本。"""
    try:
        from backend.ocr_service import extract_text
        return extract_text(image_bytes, use_angle_cls=True, use_gpu=False)
    except Exception as e:
        logger.warning("OCR 识别失败: %s", e)
        return ""


def extract_pdf_text(
    path: str,
    enable_ocr: Optional[bool] = None,
    min_text_per_page: Optional[int] = None,
) -> str:
    """
    从 PDF 提取全文：正文 + 表格；若某页字数过少则视为扫描页，用 OCR 补全。

    Args:
        path: PDF 文件路径
        enable_ocr: 是否对“疑似扫描页”启用 OCR，默认从环境变量 PDF_EXTRACT_ENABLE_OCR 读取
        min_text_per_page: 单页正文（含表格）字数低于此值则尝试 OCR，默认从 PDF_EXTRACT_MIN_TEXT_PER_PAGE 读取

    Returns:
        合并后的原始文本（未做 clean_medical_text，由调用方统一清洗）
    """
    if enable_ocr is None:
        enable_ocr = PDF_EXTRACT_ENABLE_OCR
    if min_text_per_page is None:
        min_text_per_page = PDF_EXTRACT_MIN_TEXT_PER_PAGE
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安装，无法提取 PDF")
        return ""

    page_texts: List[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                raw = _page_text_and_tables(page)
                if enable_ocr and len(raw.strip()) < min_text_per_page:
                    img_bytes = _render_page_to_png_bytes(path, i)
                    if img_bytes:
                        ocr_text = _ocr_page_image(img_bytes)
                        if ocr_text:
                            raw = ocr_text.strip()
                            logger.info("PDF 第 %s 页使用 OCR 补全，字数 %s", i + 1, len(raw))
                page_texts.append(raw)
    except Exception as e:
        logger.warning("pdfplumber 打开/遍历 PDF 失败 path=%s: %s", path, e)
        return ""

    return "\n\n".join(page_texts).strip()
