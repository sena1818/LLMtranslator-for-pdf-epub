import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.api.database.db import Database
from src.api.models.task import TaskProgress, TaskStatus, TranslationTask
from src.infrastructure.persistence.task_repository import TaskRepository


class InfrastructureAdaptersTestCase(unittest.TestCase):
    def test_task_repository_wraps_database(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                db = Database(str(Path(temp_dir) / "tasks.db"))
                repo = TaskRepository(db)
                await repo.initialize()

                task = TranslationTask(
                    task_id="repo-task",
                    filename="demo.md",
                    status=TaskStatus.PENDING,
                    bilingual=True,
                    progress=TaskProgress(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                await repo.save(task)
                loaded = await repo.get("repo-task")
                return loaded

        loaded = asyncio.run(scenario())
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, "repo-task")
        self.assertTrue(loaded.bilingual)
