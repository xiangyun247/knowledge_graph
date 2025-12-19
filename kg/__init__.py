# kg/__init__.py
"""
知识图谱模块

提供知识图谱构建功能
- KGBuilder: 从文本构建知识图谱
- TextPreprocessor: 文本预处理
"""

"""
知识图谱模块
提供知识图谱构建和管理功能
"""

from .builder import KnowledgeGraphBuilder, KGBuilder, TextPreprocessor

__all__ = [
    "KnowledgeGraphBuilder",
    "KGBuilder",  # 别名
    "TextPreprocessor",
]
