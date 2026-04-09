import asyncio
import tempfile
import unittest
import zipfile
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

    def test_zip_bundle_contains_assets_only(self):
        async def seed(db):
            await db.initialize()
            await db.save_task(
                TranslationTask(
                    task_id="zip-task",
                    filename="zip.md",
                    status=TaskStatus.COMPLETED,
                    bilingual=False,
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
            markdown_path = result_dir / "zip-task.md"
            asset_path = result_dir / "assets" / "zip-task" / "cover.jpg"
            bundle_path = result_dir / "downloads" / "zip-task.assets.zip"
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text("![cover](assets/zip-task/cover.jpg)\n", encoding="utf-8")
            asset_path.write_bytes(b"fake-image")

            try:
                app = FastAPI()
                app.include_router(files_routes.router)
                client = TestClient(app)

                response = client.get("/api/files/results/zip-task?format=zip&variant=mono")
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/zip", response.headers["content-type"])
                self.assertTrue(bundle_path.exists())

                with zipfile.ZipFile(bundle_path) as archive:
                    names = set(archive.namelist())
                    self.assertIn("assets/zip-task/cover.jpg", names)
                    self.assertNotIn("zip-task.md", names)
            finally:
                files_routes.db = original_db
                for path in [markdown_path, bundle_path, asset_path]:
                    if path.exists():
                        path.unlink()
                for directory in [
                    result_dir / "assets" / "zip-task",
                    result_dir / "assets",
                    result_dir / "downloads",
                ]:
                    if directory.exists():
                        try:
                            directory.rmdir()
                        except OSError:
                            pass

    def test_bilingual_markdown_can_backfill_mono_variant(self):
        async def seed(db):
            await db.initialize()
            await db.save_task(
                TranslationTask(
                    task_id="legacy-bi",
                    filename="legacy.md",
                    status=TaskStatus.COMPLETED,
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
            mono_path = result_dir / "legacy-bi.md"
            bilingual_path = result_dir / "legacy-bi.bilingual.md"
            bilingual_path.write_text("# 标题\n\n> source line\n\n中文译文\n\n---\n", encoding="utf-8")
            if mono_path.exists():
                mono_path.unlink()

            try:
                app = FastAPI()
                app.include_router(files_routes.router)
                client = TestClient(app)

                response = client.get("/api/files/results/legacy-bi?format=md&variant=mono")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(mono_path.exists())
                self.assertIn("中文译文", mono_path.read_text(encoding="utf-8"))
            finally:
                files_routes.db = original_db
                for path in [mono_path, bilingual_path]:
                    if path.exists():
                        path.unlink()
