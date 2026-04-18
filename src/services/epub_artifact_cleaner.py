"""
兼容层：EPUB 残留清理器

正式实现已迁移到 pipelines/preprocess。
"""
from __future__ import annotations

from ..pipelines.preprocess.artifact_cleaner import EpubArtifactCleaner

__all__ = ["EpubArtifactCleaner"]
