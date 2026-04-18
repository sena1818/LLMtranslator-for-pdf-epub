import asyncio
import tempfile
import unittest
from pathlib import Path

from src.domain.rules.chunk_planning import TextChunk
from src.infrastructure.cache.translation_cache import TranslationCache
from src.core.translator import TranslationEngine, TranslationResult


class TranslationCacheTestCase(unittest.TestCase):
    def test_cache_roundtrip(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                cache = TranslationCache(Path(temp_dir) / "cache.db")
                await cache.set(
                    cache_key="abc",
                    chunk_id="chunk-1",
                    translation="测试译文",
                    quality_report={"passed": True, "issue_count": 0, "issues": []},
                    repaired=False,
                )
                return await cache.get("abc")

        entry = asyncio.run(scenario())
        self.assertIsNotNone(entry)
        self.assertEqual(entry.chunk_id, "chunk-1")
        self.assertEqual(entry.translation, "测试译文")
        self.assertTrue(entry.quality_report["passed"])

    def test_translate_batch_uses_cache_hits(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                engine = TranslationEngine.__new__(TranslationEngine)
                engine.cache = TranslationCache(Path(temp_dir) / "cache.db")
                engine.prompt_version = "v2"
                engine.glossary = {}

                class Config:
                    model_name = "test-model"

                engine.config = Config()

                chunks = [
                    TextChunk(
                        index=0,
                        chunk_id="chunk-0",
                        text="cached chunk",
                        section_path=["Section"],
                        section_title="Section",
                        context_text="",
                    ),
                    TextChunk(
                        index=1,
                        chunk_id="chunk-1",
                        text="live chunk",
                        section_path=["Section"],
                        section_title="Section",
                        context_text="ctx",
                    ),
                ]

                engine.plan_chunks = lambda text: chunks
                engine._build_cache_key = lambda chunk: chunk.chunk_id

                live_calls = []

                async def fake_process(chunk, output_manager, callback):
                    live_calls.append(chunk.chunk_id)
                    result = TranslationResult(
                        chunk_index=chunk.index,
                        original=chunk.text,
                        translation="实时翻译",
                        success=True,
                        chunk_id=chunk.chunk_id,
                    )
                    await output_manager.add_result(
                        index=result.chunk_index,
                        content=result.translation,
                        success=True,
                        original_text=chunk.text,
                    )
                    return result

                engine._process_one_chunk = fake_process

                await engine.cache.set(
                    cache_key="chunk-0",
                    chunk_id="chunk-0",
                    translation="缓存译文",
                    quality_report={"passed": True, "issue_count": 0, "issues": []},
                    repaired=False,
                )

                output_path = Path(temp_dir) / "out.md"
                output_path.write_text("", encoding="utf-8")
                results = await TranslationEngine.translate_batch(
                    engine,
                    text="dummy",
                    output_path=output_path,
                    prepared_chunks=chunks,
                )
                return results, live_calls

        results, live_calls = asyncio.run(scenario())

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].cached)
        self.assertEqual(results[0].translation, "缓存译文")
        self.assertEqual(live_calls, ["chunk-1"])
