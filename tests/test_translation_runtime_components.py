import asyncio
import tempfile
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from src.domain.models.translation_models import DocumentProfile, TranslationResult
from src.domain.rules.chunk_planning import TextChunk
from src.pipelines.translate.batch_orchestrator import TranslationBatchOrchestrator
from src.pipelines.translate.prompt_builder import TranslationPromptBuilder
from src.pipelines.translate.translation_client import TranslationClient


def test_translation_client_retries_then_succeeds():
    class Config:
        def get(self, key, default=None):
            if key == "api.translator.max_retries":
                return 2
            return default

    class DummyRateLimiter:
        async def acquire(self):
            return None

    calls = {"count": 0}

    async def flaky_translator(payload):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "译文结果"

    client = TranslationClient(
        llm_translator=RunnableLambda(flaky_translator),
        config=Config(),
        prompt_builder=TranslationPromptBuilder(),
        rate_limiter=DummyRateLimiter(),
        clean_output=lambda text: text.strip(),
        glossary={},
    )

    async def scenario():
        return await client.translate(
            chunk=TextChunk(
                index=0,
                chunk_id="chunk-0",
                text="body",
                section_path=["Section"],
                section_title="Section",
                context_text="ctx",
            ),
            document_profile=DocumentProfile(summary="profile"),
        )

    translation, retry_count, _duration = asyncio.run(scenario())
    assert translation == "译文结果"
    assert retry_count == 1


def test_batch_orchestrator_combines_cache_and_live_results():
    class FakeCacheEntry:
        def __init__(self):
            self.translation = "缓存译文"
            self.quality_report = {"passed": True}
            self.repaired = False

    class FakeCache:
        async def get(self, cache_key):
            if cache_key == "cache-chunk-0":
                return FakeCacheEntry()
            return None

    orchestrator = TranslationBatchOrchestrator(
        cache=FakeCache(),
        build_cache_key=lambda chunk: f"cache-{chunk.chunk_id}",
    )

    chunks = [
        TextChunk(0, "chunk-0", "first", ["Section"], "Section", ""),
        TextChunk(1, "chunk-1", "second", ["Section"], "Section", ""),
    ]

    async def process_chunk(chunk, output_manager, progress_callback):
        result = TranslationResult(
            chunk_index=chunk.index,
            original=chunk.text,
            translation="实时译文",
            success=True,
            chunk_id=chunk.chunk_id,
        )
        await output_manager.add_result(
            index=result.chunk_index,
            content=result.translation,
            success=True,
            original_text=result.original,
        )
        return result

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "out.md"

        async def scenario():
            return await orchestrator.run(
                chunks=chunks,
                output_path=output_path,
                bilingual=False,
                progress_callback=None,
                process_chunk=process_chunk,
            )

        results = asyncio.run(scenario())

    assert len(results) == 2
    assert results[0].translation == "缓存译文"
    assert results[1].translation == "实时译文"
