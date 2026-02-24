#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 服务：基于 PaddleOCR 的光学字符识别
- 支持中文、表格、处方等场景
- 用于检查单、处方等图片的文字提取
"""

import logging
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


def extract_text(
    image_source: Union[str, Path, bytes],
    use_angle_cls: bool = True,
    use_gpu: bool = False,
) -> str:
    """
    从图片中提取文字。

    Args:
        image_source: 图片路径或字节
        use_angle_cls: 是否使用方向分类器（纠正旋转文字）
        use_gpu: 是否使用 GPU（PaddleOCR 3.x 使用 device 参数）

    Returns:
        识别出的文本，按行拼接
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise RuntimeError("请安装 PaddleOCR: pip install paddlepaddle paddleocr")

    # PaddleOCR 3.x 使用 device 替代 use_gpu，use_textline_orientation 替代 use_angle_cls
    # 关闭文档预处理以加快初始化、减少模型下载
    # enable_mkldnn=False 避免 Windows 下 oneDNN 兼容性错误
    ocr = PaddleOCR(
        lang="ch",
        use_textline_orientation=use_angle_cls,
        device="gpu:0" if use_gpu else "cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
    )

    # 若传入 bytes，先写入临时文件
    img_path = None
    if isinstance(image_source, bytes):
        import tempfile
        fd, img_path = tempfile.mkstemp(suffix=".png")
        with open(img_path, "wb") as f:
            f.write(image_source)
        img_path = str(img_path)
    else:
        img_path = str(image_source)

    try:
        result = ocr.predict(img_path, use_textline_orientation=use_angle_cls)
        if not result:
            return ""
        # PaddleOCR 3.x predict 返回: 每项为对象，含 res.rec_texts 或 res 为 dict
        lines = []
        for item in result:
            res = getattr(item, "res", item) if not isinstance(item, dict) else item.get("res", item)
            texts = (res.get("rec_texts") or res.get("rec_text") or []) if isinstance(res, dict) else []
            if isinstance(texts, str):
                texts = [texts]
            for t in (texts or []):
                if t:
                    lines.append(t if isinstance(t, str) else str(t))
        return "\n".join(lines).strip() if lines else ""
    finally:
        if isinstance(image_source, bytes) and img_path:
            try:
                Path(img_path).unlink(missing_ok=True)
            except Exception:
                pass


def extract_text_with_boxes(
    image_source: Union[str, Path, bytes],
    use_angle_cls: bool = True,
    use_gpu: bool = False,
) -> List[dict]:
    """
    从图片中提取文字及位置信息。

    Returns:
        [{"text": str, "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}, ...]
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise RuntimeError("请安装 PaddleOCR: pip install paddlepaddle paddleocr")

    ocr = PaddleOCR(
        lang="ch",
        use_textline_orientation=use_angle_cls,
        device="gpu:0" if use_gpu else "cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
    )

    img_path = None
    if isinstance(image_source, bytes):
        import tempfile
        fd, img_path = tempfile.mkstemp(suffix=".png")
        with open(img_path, "wb") as f:
            f.write(image_source)
        img_path = str(img_path)
    else:
        img_path = str(image_source)

    try:
        result = ocr.predict(img_path, use_textline_orientation=use_angle_cls)
        if not result:
            return []

        out = []
        for item in result:
            res = getattr(item, "res", item) if not isinstance(item, dict) else item.get("res", item)
            if not isinstance(res, dict):
                continue
            texts = res.get("rec_texts") or res.get("rec_text") or []
            polys = res.get("rec_polys") or res.get("dt_polys") or res.get("rec_boxes") or []
            if isinstance(texts, str):
                texts = [texts]
            for i, t in enumerate(texts or []):
                box = polys[i] if (polys is not None and i < len(polys)) else []
                try:
                    box = box.tolist() if hasattr(box, "tolist") else list(box) if isinstance(box, (list, tuple)) else []
                except Exception:
                    box = []
                out.append({"text": t if isinstance(t, str) else str(t), "box": box})
        return out
    finally:
        if isinstance(image_source, bytes) and img_path:
            try:
                Path(img_path).unlink(missing_ok=True)
            except Exception:
                pass
