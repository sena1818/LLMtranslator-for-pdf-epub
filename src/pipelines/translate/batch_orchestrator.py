"""
批量翻译编排器

负责：
- 缓存命中
- 输出管理器写入
- chunk 并发调度
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from ...core.chunk_planner import TextChunk
from ...core.output_manager import OutputManager
from ...domain.models.translation_models import TranslationResult


class TranslationBatchOrchestrator:
    """管理 batch 级翻译执行。"""

    def __init__(self, cache, build_cache_key: Callable[[TextChunk], str]):
        self.cache = cache
        self.build_cache_key = build_cache_key

    async def run(
        self,
        chunks: list[TextChunk],
        output_path: Path,
        bilingual: bool,
        progress_callback,
        process_chunk,
    ) -> list[TranslationResult]:
        output_manager = OutputManager(str(output_path), bilingual=bilingual)
        tasks = []
        results: list[TranslationResult] = []

        for chunk in chunks:
            cache_entry = await self.cache.get(self.build_cache_key(chunk))
            if cache_entry:
                cached_result = TranslationResult(
                    chunk_index=chunk.index,
                    original=chunk.text,
                    translation=cache_entry.translation,
                    success=True,
                    retry_count=0,
                    duration=0.0,
                    chunk_id=chunk.chunk_id,
                    quality_report=cache_entry.quality_report,
                    repaired=cache_entry.repaired,
                    cached=True,
                )
                await output_manager.add_result(
                    index=cached_result.chunk_index,
                    content=cached_result.translation,
                    success=True,
                    original_text=chunk.text,
                )
                if progress_callback:
                    await progress_callback(
                        {
                            "chunk_index": chunk.index,
                            "chunk_id": chunk.chunk_id,
                            "status": "completed",
                            "translation": cache_entry.translation,
                            "duration": 0.0,
                            "quality_report": cache_entry.quality_report,
                            "repaired": cache_entry.repaired,
                            "cached": True,
                        }
                    )
                results.append(cached_result)
                continue

            tasks.append(process_chunk(chunk, output_manager, progress_callback))

        live_results = await asyncio.gather(*tasks)
        results.extend(live_results)
        return sorted(results, key=lambda r: r.chunk_index)
