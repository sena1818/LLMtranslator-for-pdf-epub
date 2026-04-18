"""
共享翻译流水线

用于收敛 CLI 与 Web 的主翻译入口，避免两套编排逻辑继续漂移。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from ...core.chunk_planner import TextChunk
from ...core.translator import TranslationEngine, TranslationResult


ProgressCallback = Optional[Callable[[dict], Awaitable[None]]]


@dataclass
class TranslationPipelineOutput:
    """共享翻译流水线的结果对象"""

    chunks: List[TextChunk]
    results: List[TranslationResult]
    engine: TranslationEngine


class DocumentTranslationPipeline:
    """封装文本分块与批量翻译，供 CLI / API 共用。"""

    def __init__(self, glossary: Optional[Dict[str, str]] = None, engine_cls=TranslationEngine):
        self.engine = engine_cls(glossary=glossary or {})

    def plan_chunks(self, text: str) -> List[TextChunk]:
        """结构化分块"""
        return self.engine.plan_chunks(text)

    async def run(
        self,
        text: str,
        output_path: Path,
        bilingual: bool = False,
        progress_callback: ProgressCallback = None,
        prepared_chunks: Optional[List[TextChunk]] = None,
    ) -> TranslationPipelineOutput:
        """执行完整翻译"""
        chunks = prepared_chunks or self.plan_chunks(text)
        results = await self.engine.translate_batch(
            text=text,
            output_path=output_path,
            progress_callback=progress_callback,
            bilingual=bilingual,
            prepared_chunks=chunks,
        )
        return TranslationPipelineOutput(
            chunks=chunks,
            results=results,
            engine=self.engine,
        )
