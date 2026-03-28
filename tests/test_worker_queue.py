import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.api.database.db import Database
from src.api.models.task import TaskProgress, TaskStatus, TranslationTask
from src.api.worker import TaskWorker


class WorkerQueueTestCase(unittest.TestCase):
    def test_claim_next_pending_task_is_ordered_and_atomic(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                db = Database(str(Path(temp_dir) / "translation.db"))
                await db.initialize()

                first = TranslationTask(
                    task_id="task-1",
                    filename="a.md",
                    status=TaskStatus.PENDING,
                    progress=TaskProgress(),
                    created_at=datetime(2025, 1, 1, 10, 0, 0),
                    updated_at=datetime(2025, 1, 1, 10, 0, 0),
                )
                second = TranslationTask(
                    task_id="task-2",
                    filename="b.md",
                    status=TaskStatus.PENDING,
                    progress=TaskProgress(),
                    created_at=datetime(2025, 1, 1, 10, 1, 0),
                    updated_at=datetime(2025, 1, 1, 10, 1, 0),
                )
                await db.save_task(first)
                await db.save_task(second)

                claimed_first = await db.claim_next_pending_task()
                claimed_second = await db.claim_next_pending_task()
                claimed_none = await db.claim_next_pending_task()
                return claimed_first, claimed_second, claimed_none

        claimed_first, claimed_second, claimed_none = asyncio.run(scenario())
        self.assertEqual(claimed_first.task_id, "task-1")
        self.assertEqual(claimed_first.status, TaskStatus.PROCESSING)
        self.assertEqual(claimed_second.task_id, "task-2")
        self.assertEqual(claimed_second.status, TaskStatus.PROCESSING)
        self.assertIsNone(claimed_none)

    def test_requeue_stale_processing_tasks(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                db = Database(str(Path(temp_dir) / "translation.db"))
                await db.initialize()

                stale_task = TranslationTask(
                    task_id="task-stale",
                    filename="stale.md",
                    status=TaskStatus.PROCESSING,
                    progress=TaskProgress(),
                    created_at=datetime.now() - timedelta(hours=1),
                    updated_at=datetime.now() - timedelta(hours=1),
                )
                await db.save_task(stale_task)

                requeued = await db.requeue_stale_processing_tasks(stale_after_seconds=60)
                refreshed = await db.get_task("task-stale")
                return requeued, refreshed

        requeued, refreshed = asyncio.run(scenario())
        self.assertEqual(requeued, 1)
        self.assertEqual(refreshed.status, TaskStatus.PENDING)
        self.assertIn("重新排队", refreshed.error)

    def test_worker_respects_max_parallel_tasks(self):
        async def scenario():
            class FakeTask:
                def __init__(self, task_id: str):
                    self.task_id = task_id
                    self.filename = f"{task_id}.md"

            class FakeService:
                def __init__(self):
                    self.pending = [FakeTask("task-1"), FakeTask("task-2"), FakeTask("task-3")]
                    self.inflight = 0
                    self.max_seen = 0
                    self.started = []

                async def claim_next_pending_task(self):
                    return self.pending.pop(0) if self.pending else None

                async def start_translation(self, task_id: str, already_claimed: bool = False):
                    self.started.append(task_id)
                    self.inflight += 1
                    self.max_seen = max(self.max_seen, self.inflight)
                    await asyncio.sleep(0.01)
                    self.inflight -= 1

            worker = TaskWorker(max_parallel_tasks=2, poll_interval=0.001)
            worker.service = FakeService()
            await worker.run_until_idle()
            return worker.service.started, worker.service.max_seen

        started, max_seen = asyncio.run(scenario())
        self.assertEqual(started, ["task-1", "task-2", "task-3"])
        self.assertLessEqual(max_seen, 2)
