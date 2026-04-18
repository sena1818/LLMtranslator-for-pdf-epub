"""
兼容导出：结构化分块器

真实实现已迁移到 `src/domain/rules/chunk_planning.py`。
"""

from ..domain.rules.chunk_planning import ChunkPlanner, TextBlock, TextChunk

__all__ = ["ChunkPlanner", "TextBlock", "TextChunk"]
