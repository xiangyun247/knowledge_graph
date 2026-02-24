#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS 服务：基于 Edge-TTS 的文本转语音
- 支持中文朗读，用于患者教育「读给你听」
- 生成 MP3 音频文件或返回字节流
"""

import asyncio
import io
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# 默认中文女声（微软 Edge 在线语音）
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
# 备选：zh-CN-YunxiNeural（男声）


async def synthesize_tts(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    volume: str = "+0%",
) -> bytes:
    """
    将文本转为语音，返回 MP3 字节流。

    Args:
        text: 要朗读的文本
        voice: 语音名称，默认 zh-CN-XiaoxiaoNeural
        rate: 语速，如 "+10%" 加快、"-10%" 减慢
        volume: 音量，如 "+10%" 增大

    Returns:
        MP3 格式的音频字节
    """
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("请安装 edge-tts: pip install edge-tts")

    if not text or not text.strip():
        raise ValueError("文本不能为空")

    text = text.strip()
    # Edge-TTS 单次请求有长度限制，建议分段
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars] + "（内容已截断）"

    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def synthesize_tts_sync(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    volume: str = "+0%",
) -> bytes:
    """同步版本，供非 async 上下文调用。"""
    return asyncio.run(synthesize_tts(text, voice, rate, volume))


def synthesize_to_file(
    text: str,
    output_path: Optional[str] = None,
    voice: str = DEFAULT_VOICE,
) -> str:
    """
    将文本转为语音并保存到文件。

    Returns:
        保存后的文件路径
    """
    audio_bytes = synthesize_tts_sync(text, voice)
    if not output_path:
        fd, output_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    return output_path
