"""
应用层用例：运行翻译流水线
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from ...core.translator import TranslationEngine
from ...pipelines.translate.document_translation_pipeline import (
    DocumentTranslationPipeline,
    TranslationPipelineOutput,
)

ProgressCallback = Callable[[dict], Awaitable[None]] | None


class RunTranslationPipeline:
    """供 CLI / Web 共用的应用层翻译用例。"""

    def __init__(self, glossary: dict[str, str] | None = None, engine_cls=TranslationEngine):
        self.pipeline = DocumentTranslationPipeline(glossary=glossary or {}, engine_cls=engine_cls)

    def plan_chunks(self, text: str):
        return self.pipeline.plan_chunks(text)

    async def execute(
        self,
        text: str,
        output_path: Path,
        bilingual: bool = False,
        progress_callback: ProgressCallback = None,
        prepared_chunks=None,
    ) -> TranslationPipelineOutput:
        return await self.pipeline.run(
            text=text,
            output_path=output_path,
            bilingual=bilingual,
            progress_callback=progress_callback,
            prepared_chunks=prepared_chunks,
        )
