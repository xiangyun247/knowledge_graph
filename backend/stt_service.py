#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STT 服务：基于 OpenAI Whisper 的语音转文本
- 支持中文识别，用于问答输入框的语音输入
- 可本地运行，无需 API Key
"""

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 模型大小：tiny(75M) / base(142M) / small(466M) / medium(1.5G)
# tiny 适合 CPU，small 及以上建议 GPU
DEFAULT_MODEL = "base"


def _ensure_ffmpeg_in_path() -> None:
  """
  确保当前进程 PATH 中包含 ffmpeg 路径：
  - 优先从 .env 的 FFMPEG_BIN_DIR 读取
  - 若未配置则不做任何修改
  """
  # 只在第一次调用时加载 .env，避免每次 transcribe 都重复解析
  load_dotenv()
  ffmpeg_dir = os.getenv("FFMPEG_BIN_DIR") or ""
  if not ffmpeg_dir or not os.path.isdir(ffmpeg_dir):
      return
  path = os.environ.get("PATH", "")
  if ffmpeg_dir not in path:
      os.environ["PATH"] = ffmpeg_dir + os.pathsep + path


def transcribe(
    audio_source: Union[bytes, str, Path],
    model_size: str = DEFAULT_MODEL,
    language: Optional[str] = "zh",
    audio_format: Optional[str] = None,
) -> str:
    """
    将音频转为文本。

    Args:
        audio_source: 音频文件路径、或音频字节（bytes）
        model_size: 模型大小，tiny/base/small
        language: 语言代码，zh 为中文
        audio_format: 当 audio_source 为 bytes 时，指定格式如 .wav/.mp3/.webm

    Returns:
        识别出的文本
    """
    try:
        import whisper
    except ImportError:
        raise RuntimeError("请安装 openai-whisper: pip install openai-whisper")

    # 使用 .env 中的 FFMPEG_BIN_DIR 确保 ffmpeg 命令可用
    _ensure_ffmpeg_in_path()

    # 若传入 bytes，先写入临时文件
    audio_path = None
    if isinstance(audio_source, bytes):
        suffix = audio_format or ".wav"
        if not suffix.startswith("."):
            suffix = "." + suffix
        fd, audio_path = tempfile.mkstemp(suffix=suffix)
        with open(audio_path, "wb") as f:
            f.write(audio_source)
        audio_path = Path(audio_path)
    elif isinstance(audio_source, str):
        audio_path = Path(audio_source)
    else:
        audio_path = Path(audio_source)

    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(
            str(audio_path),
            language=language,
            fp16=False,  # CPU 下用 fp16=False
        )
        return (result.get("text") or "").strip()
    finally:
        if isinstance(audio_source, bytes) and audio_path and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass
