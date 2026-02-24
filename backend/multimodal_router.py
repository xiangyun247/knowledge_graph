#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态 API：TTS、STT、OCR
"""

import asyncio
import io
import logging
import re
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["多模态"])


def _strip_markdown(text: str) -> str:
    """移除 Markdown 格式符号（#、* 等），输出纯文本。"""
    if not text:
        return ""
    s = str(text)
    # 去掉行首的 #、##、### 等
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.MULTILINE)
    # **粗体** -> 粗体，*斜体* -> 斜体
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]*)\*", r"\1", s)
    s = s.replace("*", "").replace("#", "")
    return s.strip()


# ---------- TTS ----------

class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str = Field(..., min_length=1, max_length=10000, description="要朗读的文本")
    voice: str = Field("zh-CN-XiaoxiaoNeural", description="语音名称")
    rate: str = Field("+0%", description="语速")
    volume: str = Field("+0%", description="音量")


@router.post("/tts/synthesize")
async def api_tts_synthesize(req: TTSRequest):
    """
    文本转语音，返回 MP3 音频。
    """
    try:
        from backend.tts_service import synthesize_tts
        audio_bytes = await synthesize_tts(
            text=req.text,
            voice=req.voice,
            rate=req.rate,
            volume=req.volume,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail="TTS 服务不可用，请安装 edge-tts: pip install edge-tts")
    except Exception as e:
        logger.exception("TTS 合成失败")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- STT ----------

@router.post("/stt/transcribe")
async def api_stt_transcribe(audio: UploadFile = File(...)):
    """
    语音转文本，接收音频文件（wav/mp3/m4a/webm 等）。
    """
    try:
        from backend.stt_service import transcribe
        content = await audio.read()
        if not content:
            raise HTTPException(status_code=400, detail="音频文件为空")
        # 从文件名推断格式
        ext = ""
        if audio.filename:
            for p in (".wav", ".mp3", ".m4a", ".webm", ".ogg"):
                if p in audio.filename.lower():
                    ext = p
                    break
        if not ext:
            ext = ".wav"
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            lambda: transcribe(content, model_size="base", language="zh", audio_format=ext),
        )
        return {"text": text}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="STT 服务不可用，请安装 openai-whisper: pip install openai-whisper")
    except Exception as e:
        logger.exception("STT 识别失败")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- OCR ----------

@router.post("/ocr/extract")
async def api_ocr_extract(image: UploadFile = File(...)):
    """
    从图片中提取文字。支持检查单、处方等。
    """
    try:
        from backend.ocr_service import extract_text
        content = await image.read()
        if not content:
            raise HTTPException(status_code=400, detail="图片文件为空")
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            lambda: extract_text(content, use_angle_cls=True, use_gpu=False),
        )
        return {"text": text}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="OCR 服务不可用，请安装 paddlepaddle paddleocr")
    except Exception as e:
        logger.exception("OCR 提取失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr/interpret")
async def api_ocr_interpret(image: UploadFile = File(...)):
    """
    从图片中提取文字，并调用 LLM 生成通俗解读（面向患者的检查单/处方解读）。
    """
    try:
        from backend.ocr_service import extract_text
        from llm.client import LLMClient
        content = await image.read()
        if not content:
            raise HTTPException(status_code=400, detail="图片文件为空")
        loop = asyncio.get_event_loop()
        ocr_text = await loop.run_in_executor(
            None,
            lambda: extract_text(content, use_angle_cls=True, use_gpu=False),
        )
        if not ocr_text or not ocr_text.strip():
            return {"text": "", "interpretation": "未能从图片中识别出文字，请确保图片清晰、文字可辨。"}

        prompt = f"""以下是从一张医疗相关图片（可能是检查单、处方、报告等）中识别出的文字：

---
{ocr_text}
---

请用通俗易懂的语言，面向普通患者做简要解读：
1. 概括图片内容类型（如检查结果、处方等）
2. 逐项说明关键指标或药物的含义
3. 提醒需要注意的事项
4. 结尾加「以上解读仅供参考，具体请遵医嘱」

要求：直接输出纯文本解读，不要使用 Markdown 格式（不要用 #、##、### 或 **、* 等符号）。"""

        client = LLMClient()
        messages = [
            {"role": "system", "content": "你是一名耐心的医疗科普助手，擅长用通俗语言向患者解释检查单、处方等医疗文书。"},
            {"role": "user", "content": prompt},
        ]
        interpretation = await loop.run_in_executor(
            None,
            lambda: client.chat(messages, temperature=0.5, max_tokens=1500),
        )
        interpretation = (interpretation or "").strip()
        interpretation = _strip_markdown(interpretation)

        return {"text": ocr_text, "interpretation": interpretation}
    except ImportError as e:
        if "paddleocr" in str(e).lower() or "paddle" in str(e).lower():
            raise HTTPException(status_code=503, detail="OCR 服务不可用，请安装 paddlepaddle paddleocr")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("OCR 解读失败")
        raise HTTPException(status_code=500, detail=str(e))
