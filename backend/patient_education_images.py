#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者教育配图生成封装

- 基于 GLM-Image 文生图，为患者教育的小节生成插画
- 暴露 generate_section_images_glm(title, sections) 给 API 使用
"""

import logging
from typing import Dict, List

from .glm_image_client import call_glm_image

logger = logging.getLogger(__name__)


def _build_section_prompt(title: str, heading: str, content: str) -> str:
    """
    将患者教育小节转成适合 GLM-Image 的中文 Prompt。
    尽量强调：医疗科普插画、无血腥、温和风格。
    """
    return f"""
你是一名医学插画师，请为一篇面向普通患者的科普文章生成一张插画。

文章标题：{title}
本小节标题：{heading}
本小节要表达的要点简要概括如下（仅供理解，不要画成文字说明书）：
{(content or '')[:260]}

绘画要求：
- 场景：医疗科普/健康教育插画，适合医院/科室的患者宣教材料
- 风格：温和、简洁、扁平或插画风，颜色柔和，避免夸张和恐怖
- 内容：避免血腥、手术细节和真实面部特写，不出现具体患者隐私信息
- 主题聚焦在疾病原理示意、出院后护理场景或日常饮食生活方式引导
"""


def generate_section_images_glm(
    title: str,
    sections: List[Dict],
    max_images: int = 4,
    size: str = "1280x1280",
) -> List[Dict]:
    """
    针对患者教育的每个小节调用 GLM-Image 生成插图。

    Args:
        title: 患者教育整体标题
        sections: [{heading, content}, ...]
        max_images: 最多生成多少张图（从前若干小节中选取）
        size: 图片尺寸

    Returns:
        [{ section_index, url, prompt }, ...]
    """
    results: List[Dict] = []
    if not sections:
        return results

    for idx, sec in enumerate(sections[:max_images]):
        heading = (sec.get("heading") or "").strip()
        content = (sec.get("content") or "").strip()
        if not heading and not content:
            continue

        prompt = _build_section_prompt(title, heading, content)
        try:
            url = call_glm_image(prompt=prompt, size=size)
            results.append(
                {
                    "section_index": idx,
                    "url": url,
                    "prompt": prompt.strip(),
                }
            )
        except Exception as e:
            logger.warning("患者教育配图生成失败: section=%s, error=%s", idx, e)
            continue

    return results

