"""
任务仓储适配器

将应用层/服务层与具体 SQLite Database 实现解耦。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from ...api.database.db import Database
from ...domain.models.task_models import TranslationTask


class TaskRepository:
    """翻译任务仓储。"""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    async def initialize(self):
        await self.db.initialize()

    async def save(self, task: TranslationTask):
        await self.db.save_task(task)

    async def update(self, task: TranslationTask):
        await self.db.update_task(task)

    async def get(self, task_id: str) -> Optional[TranslationTask]:
        return await self.db.get_task(task_id)

    async def list(self, skip: int = 0, limit: int = 20) -> Tuple[List[TranslationTask], int]:
        return await self.db.list_tasks(skip, limit)

    async def delete(self, task_id: str) -> bool:
        return await self.db.delete_task(task_id)

    async def claim_next_pending(self) -> Optional[TranslationTask]:
        return await self.db.claim_next_pending_task()

    async def requeue_stale_processing(self, stale_after_seconds: int = 900) -> int:
        return await self.db.requeue_stale_processing_tasks(stale_after_seconds)
