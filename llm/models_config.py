#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多 LLM 模型配置：DeepSeek、GPT、Gemini、通义、豆包、智谱、文心一言、Kimi、Grok 等。
未配置 API Key 的模型也会出现在列表中，但 configured=False；前端可提示「未配置该模型」。
"""

import os
from typing import List, Dict, Any, Optional, Tuple

def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()

# 模型定义：id -> { name, api_key_env, base_url, model?, model_env? }
# base_url 若不含 /v1 会自动追加
LLM_MODELS: Dict[str, Dict[str, Any]] = {
    # ========== DeepSeek ==========
    "deepseek-chat": {
        "name": "DeepSeek Chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    },
    "deepseek-reasoner": {
        "name": "DeepSeek R1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-reasoner",
    },
    # ========== 通义千问 ==========
    "qwen-plus": {
        "name": "通义千问 Plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "qwen-max": {
        "name": "通义千问 Max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
    },
    "qwen-turbo": {
        "name": "通义千问 Turbo",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
    },
    # ========== 豆包（火山引擎） ==========
    "doubao-pro": {
        "name": "豆包 Pro",
        "api_key_env": "ARK_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_env": "ARK_MODEL",
        "model": "doubao-pro-32k",
    },
    "doubao-pro-32k": {
        "name": "豆包 Pro 32K",
        "api_key_env": "ARK_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_env": "ARK_MODEL",
        "model": "doubao-pro-32k",
    },
    # ========== OpenAI GPT ==========
    "gpt-4o": {
        "name": "GPT-4o",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        "model": "gpt-4o",
    },
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        "model": "gpt-4o-mini",
    },
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        "model": "gpt-4-turbo",
    },
    "gpt-4o-2024-11": {
        "name": "GPT-4o (2024-11)",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        "model": "gpt-4o-2024-11-20",
    },
    # ========== Google Gemini ==========
    "gemini-1.5-pro": {
        "name": "Gemini 1.5 Pro",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-1.5-pro",
    },
    "gemini-1.5-flash": {
        "name": "Gemini 1.5 Flash",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-1.5-flash",
    },
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash-exp",
    },
    # ========== xAI Grok ==========
    "grok-2": {
        "name": "Grok 2",
        "api_key_env": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-2",
    },
    "grok-2-mini": {
        "name": "Grok 2 Mini",
        "api_key_env": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-2-mini",
    },
    # ========== 智谱 GLM ==========
    "glm-4-plus": {
        "name": "智谱 GLM-4 Plus",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
    "glm-4-flash": {
        "name": "智谱 GLM-4 Flash",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "glm-4": {
        "name": "智谱 GLM-4",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4",
    },
    # ========== 文心一言 ==========
    "ernie-4.0": {
        "name": "文心一言 ERNIE-4.0",
        "api_key_env": "WENXIN_API_KEY",
        "base_url": os.getenv("WENXIN_BASE_URL", "https://aip.baidubce.com"),
        "model": "completions_pro",  # 以百度实际 model 名为准，可配 WENXIN_MODEL
        "model_env": "WENXIN_MODEL",
    },
    "ernie-3.5": {
        "name": "文心一言 ERNIE-3.5",
        "api_key_env": "WENXIN_API_KEY",
        "base_url": os.getenv("WENXIN_BASE_URL", "https://aip.baidubce.com"),
        "model": "ernie_speed",
        "model_env": "WENXIN_MODEL",
    },
    # ========== Kimi 月之暗面 ==========
    "kimi-moonshot-v1-8k": {
        "name": "Kimi Moonshot 8K",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "kimi-moonshot-v1-32k": {
        "name": "Kimi Moonshot 32K",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-32k",
    },
    "kimi-moonshot-v1-128k": {
        "name": "Kimi Moonshot 128K",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-128k",
    },
    "kimi-moonshot-v1": {
        "name": "Kimi Moonshot",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1",
    },
}


def get_llm_config(model_id: str) -> Optional[Tuple[str, str, str]]:
    """
    根据 model_id 获取 (api_key, base_url, model)。
    若该模型未配置 API Key，返回 None。
    """
    if not model_id or model_id not in LLM_MODELS:
        return None
    cfg = LLM_MODELS[model_id]
    api_key = _env(cfg["api_key_env"])
    if not api_key:
        return None
    base_url = (cfg.get("base_url") or "").rstrip("/")
    # 部分厂商 base 已含路径（如 Gemini /openai），不再追加 /v1
    if "/v1" not in base_url and "/v1beta" not in base_url and "/v4" not in base_url:
        base_url = base_url + "/v1"
    model_env = cfg.get("model_env")
    model = _env(model_env) if model_env else None
    model = model or cfg.get("model") or model_id
    return (api_key, base_url, model)


def _is_configured(model_id: str) -> bool:
    return get_llm_config(model_id) is not None


def get_all_models() -> List[Dict[str, Any]]:
    """
    返回全部模型列表（含未配置），每项带 configured: bool。
    前端可展示全部选项，未配置的点击/发送时提示「未配置该模型」。
    """
    out = []
    for mid, cfg in LLM_MODELS.items():
        configured = _is_configured(mid)
        out.append({
            "id": mid,
            "name": cfg.get("name", mid),
            "model": cfg.get("model", mid),
            "configured": configured,
        })
    return out


def get_available_models() -> List[Dict[str, Any]]:
    """
    返回已配置 API Key 的模型列表（兼容旧逻辑）。
    """
    return [m for m in get_all_models() if m.get("configured")]


def get_default_model_id() -> str:
    """返回默认模型 id（第一个已配置的）。"""
    avail = get_available_models()
    if avail:
        return avail[0]["id"]
    return "deepseek-chat"
