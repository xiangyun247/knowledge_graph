"""
LLM 模块 - 大语言模型客户端封装

提供 DeepSeek API 的统一接口
"""
from .client import DeepSeekClient, LLMClient, EmbeddingClient

__version__ = "1.0.0"

__all__ = [
    'DeepSeekClient',
    'LLMClient',
    'EmbeddingClient'  # ← 新增
]
