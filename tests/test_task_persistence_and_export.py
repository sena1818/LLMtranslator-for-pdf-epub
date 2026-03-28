import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.database.db import Database
from src.api.models.task import TaskProgress, TaskStatus, TranslationTask
from src.api.routes import files as files_routes


class TaskPersistenceAndExportTestCase(unittest.TestCase):
    def test_bilingual_flag_roundtrip(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = Path(temp_dir) / "translation.db"
                db = Database(str(db_path))
                await db.initialize()

                task = TranslationTask(
                    task_id="task-1",
                    filename="sample.md",
                    status=TaskStatus.PENDING,
                    bilingual=True,
                    progress=TaskProgress(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                await db.save_task(task)
                loaded = await db.get_task("task-1")
                return loaded

        loaded = asyncio.run(scenario())
        self.assertTrue(loaded.bilingual)

    def test_html_export_requires_bilingual_task(self):
        async def seed(db):
            await db.initialize()
            await db.save_task(
                TranslationTask(
                    task_id="mono-task",
                    filename="mono.md",
                    status=TaskStatus.COMPLETED,
                    bilingual=False,
                    progress=TaskProgress(current=1, total=1, percentage=100.0),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            await db.save_task(
                TranslationTask(
                    task_id="bi-task",
                    filename="bi.md",
                    status=TaskStatus.PARTIAL_SUCCESS,
                    bilingual=True,
                    progress=TaskProgress(current=1, total=1, percentage=100.0),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(str(Path(temp_dir) / "translation.db"))
            asyncio.run(seed(db))

            original_db = files_routes.db
            files_routes.db = db

            result_dir = Path("data/results")
            result_dir.mkdir(parents=True, exist_ok=True)
            mono_path = result_dir / "mono-task.md"
            bi_path = result_dir / "bi-task.md"
            html_path = result_dir / "bi-task.html"

            mono_path.write_text("# demo\n\n单语内容\n", encoding="utf-8")
            bi_path.write_text("> source\n\n译文\n\n---\n", encoding="utf-8")

            try:
                app = FastAPI()
                app.include_router(files_routes.router)
                client = TestClient(app)

                mono_response = client.get("/api/files/results/mono-task?format=html")
                self.assertEqual(mono_response.status_code, 400)
                self.assertIn("仅双语任务支持", mono_response.json()["detail"])

                bi_response = client.get("/api/files/results/bi-task?format=html")
                self.assertEqual(bi_response.status_code, 200)
                self.assertIn("text/html", bi_response.headers["content-type"])
            finally:
                files_routes.db = original_db
                for path in [mono_path, bi_path, html_path]:
                    if path.exists():
                        path.unlink()
