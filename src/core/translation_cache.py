"""
兼容导出：翻译缓存

真实实现已迁移到 `src/infrastructure/cache/translation_cache.py`。
"""

from ..infrastructure.cache.translation_cache import CacheEntry, TranslationCache

__all__ = ["CacheEntry", "TranslationCache"]
