"""
应用层用例：运行翻译流水线
"""
from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

from ...core.translator import TranslationEngine
from ...pipelines.translate.document_translation_pipeline import (
    DocumentTranslationPipeline,
    TranslationPipelineOutput,
)


ProgressCallback = Optional[Callable[[dict], Awaitable[None]]]


class RunTranslationPipeline:
    """供 CLI / Web 共用的应用层翻译用例。"""

    def __init__(self, glossary: Optional[Dict[str, str]] = None, engine_cls=TranslationEngine):
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
