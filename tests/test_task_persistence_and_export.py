import asyncio
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.database.db import Database
from src.api.models.task import TaskProgress, TaskStatus, TranslationTask
from src.api.routes import files as files_routes


def test_bilingual_flag_roundtrip():
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
    assert loaded.bilingual


def test_html_export_requires_bilingual_task():
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
            assert mono_response.status_code == 400
            assert "仅双语任务支持" in mono_response.json()["detail"]

            bi_response = client.get("/api/files/results/bi-task?format=html")
            assert bi_response.status_code == 200
            assert "text/html" in bi_response.headers["content-type"]
        finally:
            files_routes.db = original_db
            for path in [mono_path, bi_path, html_path]:
                if path.exists():
                    path.unlink()


def test_zip_bundle_contains_assets_only():
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
            assert response.status_code == 200
            assert "application/zip" in response.headers["content-type"]
            assert bundle_path.exists()

            with zipfile.ZipFile(bundle_path) as archive:
                names = set(archive.namelist())
                assert "assets/zip-task/cover.jpg" in names
                assert "zip-task.md" not in names
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


def test_preview_endpoint_returns_paragraphs_for_bilingual_task():
    async def seed(db):
        await db.initialize()
        await db.save_task(
            TranslationTask(
                task_id="preview-bi",
                filename="preview.md",
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
        bilingual_path = result_dir / "preview-bi.bilingual.md"
        bilingual_path.write_text(
            "> Hyperstition works.\n\n超虚构在起作用。\n\n---\n"
            "> The desert grows.\n\n沙漠在蔓延。\n\n---\n",
            encoding="utf-8",
        )

        try:
            app = FastAPI()
            app.include_router(files_routes.router)
            client = TestClient(app)

            response = client.get("/api/files/results/preview-bi/preview")
            assert response.status_code == 200
            body = response.json()
            assert body["bilingual"] is True
            assert body["count"] == 2
            assert body["paragraphs"][0]["source"] == "Hyperstition works."
            assert body["paragraphs"][0]["translation"] == "超虚构在起作用。"
        finally:
            files_routes.db = original_db
            mono_path = result_dir / "preview-bi.md"
            for path in [bilingual_path, mono_path]:
                if path.exists():
                    path.unlink()


def test_preview_endpoint_rejects_mono_task():
    async def seed(db):
        await db.initialize()
        await db.save_task(
            TranslationTask(
                task_id="preview-mono",
                filename="preview-mono.md",
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

        try:
            app = FastAPI()
            app.include_router(files_routes.router)
            client = TestClient(app)

            response = client.get("/api/files/results/preview-mono/preview")
            assert response.status_code == 400
            assert "仅双语任务支持" in response.json()["detail"]
        finally:
            files_routes.db = original_db


def test_preview_endpoint_rejects_unfinished_task():
    async def seed(db):
        await db.initialize()
        await db.save_task(
            TranslationTask(
                task_id="preview-pending",
                filename="preview-pending.md",
                status=TaskStatus.PROCESSING,
                bilingual=True,
                progress=TaskProgress(current=1, total=4, percentage=25.0),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        db = Database(str(Path(temp_dir) / "translation.db"))
        asyncio.run(seed(db))

        original_db = files_routes.db
        files_routes.db = db

        try:
            app = FastAPI()
            app.include_router(files_routes.router)
            client = TestClient(app)

            response = client.get("/api/files/results/preview-pending/preview")
            assert response.status_code == 400
            assert "尚未完成" in response.json()["detail"]
        finally:
            files_routes.db = original_db


def test_bilingual_markdown_can_backfill_mono_variant():
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
            assert response.status_code == 200
            assert mono_path.exists()
            assert "中文译文" in mono_path.read_text(encoding="utf-8")
        finally:
            files_routes.db = original_db
            for path in [mono_path, bilingual_path]:
                if path.exists():
                    path.unlink()
