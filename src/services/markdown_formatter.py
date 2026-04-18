"""
兼容层：Markdown 格式化器

正式实现已迁移到 pipelines/postprocess。
"""
from __future__ import annotations

from ..pipelines.postprocess.markdown_formatter import BlockNode, SmartMarkdownFormatter

__all__ = ["BlockNode", "SmartMarkdownFormatter"]
