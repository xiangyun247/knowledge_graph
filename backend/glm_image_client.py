#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLM-Image 客户端封装

用途：
- 为患者教育等场景提供文生图能力
- 对上层暴露简单的 call_glm_image(prompt, size) 接口

注意：
- API Key 从 config.ZHIPU_API_KEY / 环境变量中读取，不要硬编码
"""

import logging
from typing import Optional

import requests

try:
    import config
except Exception:  # pragma: no cover - 极端情况下 config 导入失败
    config = None  # type: ignore

logger = logging.getLogger(__name__)

GLM_IMAGE_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/images/generations"


def _get_api_key() -> Optional[str]:
    """
    获取 ZHIPU_API_KEY，优先从 config.ZHIPU_API_KEY 读取，其次从环境变量。
    """
    if config is not None:
        key = getattr(config, "ZHIPU_API_KEY", "") or ""
        if key:
            return key

    import os

    key = os.getenv("ZHIPU_API_KEY", "")
    return key or None


def call_glm_image(prompt: str, size: str = "1280x1280", timeout: int = 60) -> str:
    """
    调用 GLM-Image 生成一张图，返回图片 URL。

    Args:
        prompt: 文本提示词（中文友好）
        size: 图片尺寸，默认 1280x1280；需符合官方限制
        timeout: 请求超时时间（秒）

    Returns:
        图片 URL 字符串

    Raises:
        RuntimeError: 当 API Key 未配置或接口调用失败时
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("ZHIPU_API_KEY 未配置，无法调用 GLM-Image 文生图接口")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-image",
        "prompt": prompt[:1000],
        "size": size,
        "n": 1,
    }

    logger.info("调用 GLM-Image 生成图片: size=%s", size)
    resp = requests.post(GLM_IMAGE_ENDPOINT, json=payload, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        logger.error("GLM-Image 调用失败: status=%s, body=%s", resp.status_code, resp.text[:500])
        raise RuntimeError(f"GLM-Image 调用失败: HTTP {resp.status_code}")

    data = resp.json()
    # 文档示例：response.data[0].url
    try:
        items = data.get("data") or []
        if not items:
            raise ValueError("响应中缺少 data 字段")
        url = items[0].get("url")
        if not url:
            raise ValueError("响应中缺少 url 字段")
        return url
    except Exception as e:
        logger.error("解析 GLM-Image 响应失败: %s; 原始响应: %s", e, str(data)[:500])
        raise RuntimeError(f"GLM-Image 响应解析失败: {e}")

