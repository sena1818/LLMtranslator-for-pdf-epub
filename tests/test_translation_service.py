import asyncio
import tempfile
import unittest
from pathlib import Path

from src.api.database.db import Database
from src.api.services import translation_service as translation_service_module
from src.core.chunk_planner import TextChunk
from src.core.translator import TranslationResult


class FakeConverter:
    def convert(self, input_path, output_dir):
        return input_path


class FakeEngine:
    def __init__(self, glossary=None):
        self.glossary = glossary or {}

    def plan_chunks(self, text):
        return [
            TextChunk(
                index=0,
                chunk_id="chunk-0",
                text="chunk-0",
                section_path=["Section A"],
                section_title="Section A",
                context_text="",
            ),
            TextChunk(
                index=1,
                chunk_id="chunk-1",
                text="chunk-1",
                section_path=["Section A"],
                section_title="Section A",
                context_text="上一块末尾",
            ),
        ]

    def split_text(self, text):
        return ["chunk-0", "chunk-1"]

    async def translate_batch(self, text, output_path, progress_callback=None, bilingual=False, prepared_chunks=None):
        if progress_callback:
            await progress_callback({"chunk_index": 0, "status": "completed", "translation": "译文 1"})
            await progress_callback({"chunk_index": 1, "status": "failed", "error": "mock failure"})

        return [
            TranslationResult(0, "chunk-0", "译文 1", True),
            TranslationResult(1, "chunk-1", "[翻译失败]", False),
        ]


class TranslationServiceStatusTestCase(unittest.TestCase):
    def test_partial_success_status_is_persisted(self):
        async def scenario():
            original_engine = translation_service_module.TranslationEngine
            original_converter = translation_service_module.DocumentConverter
            temp_dir = tempfile.TemporaryDirectory()
            test_db_path = Path(temp_dir.name) / "translation.db"
            task = None

            translation_service_module.TranslationEngine = FakeEngine
            translation_service_module.DocumentConverter = FakeConverter

            service = translation_service_module.TranslationService()
            service.db = Database(str(test_db_path))
            await service.db.initialize()

            try:
                task = await service.create_task(
                    file_content=b"# title\n\nmock body\n",
                    filename="service_case.md",
                    bilingual=True,
                )
                await service.start_translation(task.task_id)
                saved = await service.get_task(task.task_id)
                return task.task_id, saved
            finally:
                translation_service_module.TranslationEngine = original_engine
                translation_service_module.DocumentConverter = original_converter

                if task is not None:
                    upload_path = Path("data/uploads") / f"{task.task_id}_service_case.md"
                    result_path = Path("data/results") / f"{task.task_id}.md"
                    if upload_path.exists():
                        upload_path.unlink()
                    if result_path.exists():
                        result_path.unlink()
                temp_dir.cleanup()

        task_id, saved = asyncio.run(scenario())

        self.assertEqual(saved.status.value, "partial_success")
        self.assertTrue(saved.bilingual)
        self.assertEqual(saved.progress.current, 2)
        self.assertEqual(saved.result_url, f"/api/files/results/{task_id}")
        self.assertIn("失败块索引", saved.error)
