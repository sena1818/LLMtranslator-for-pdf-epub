"""
SQLite 数据库管理
"""
import aiosqlite
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

from ..models.task import TranslationTask, TaskStatus, TaskProgress


class Database:
    """SQLite 数据库管理"""

    def __init__(self, db_path: str = "data/translation.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    glossary_id TEXT,
                    bilingual INTEGER DEFAULT 0,
                    progress_current INTEGER DEFAULT 0,
                    progress_total INTEGER DEFAULT 0,
                    progress_percentage REAL DEFAULT 0.0,
                    progress_speed REAL DEFAULT 0.0,
                    progress_elapsed REAL DEFAULT 0.0,
                    result_url TEXT,
                    error TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            async with db.execute("PRAGMA table_info(tasks)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}

            if "bilingual" not in columns:
                await db.execute(
                    "ALTER TABLE tasks ADD COLUMN bilingual INTEGER DEFAULT 0"
                )

            await db.commit()

    async def save_task(self, task: TranslationTask):
        """保存任务"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tasks (
                    task_id,
                    filename,
                    status,
                    glossary_id,
                    bilingual,
                    progress_current,
                    progress_total,
                    progress_percentage,
                    progress_speed,
                    progress_elapsed,
                    result_url,
                    error,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.filename,
                task.status.value if isinstance(task.status, TaskStatus) else task.status,
                task.glossary_id,
                int(task.bilingual),
                task.progress.current if task.progress else 0,
                task.progress.total if task.progress else 0,
                task.progress.percentage if task.progress else 0.0,
                task.progress.speed if task.progress else 0.0,
                task.progress.elapsed if task.progress else 0.0,
                task.result_url,
                task.error,
                task.created_at.isoformat() if task.created_at else None,
                task.updated_at.isoformat() if task.updated_at else None
            ))
            await db.commit()

    async def update_task(self, task: TranslationTask):
        """更新任务"""
        task.updated_at = datetime.now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tasks SET
                    status = ?,
                    bilingual = ?,
                    progress_current = ?,
                    progress_total = ?,
                    progress_percentage = ?,
                    progress_speed = ?,
                    progress_elapsed = ?,
                    result_url = ?,
                    error = ?,
                    updated_at = ?
                WHERE task_id = ?
            """, (
                task.status.value if isinstance(task.status, TaskStatus) else task.status,
                int(task.bilingual),
                task.progress.current if task.progress else 0,
                task.progress.total if task.progress else 0,
                task.progress.percentage if task.progress else 0.0,
                task.progress.speed if task.progress else 0.0,
                task.progress.elapsed if task.progress else 0.0,
                task.result_url,
                task.error,
                task.updated_at.isoformat(),
                task.task_id
            ))
            await db.commit()

    async def get_task(self, task_id: str) -> Optional[TranslationTask]:
        """获取任务"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()

                if not row:
                    return None

                return self._row_to_task(row)

    async def list_tasks(self, skip: int = 0, limit: int = 20) -> Tuple[List[TranslationTask], int]:
        """获取任务列表"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # 总数
            async with db.execute("SELECT COUNT(*) FROM tasks") as cursor:
                total = (await cursor.fetchone())[0]

            # 分页查询
            async with db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, skip)
            ) as cursor:
                rows = await cursor.fetchall()
                tasks = [self._row_to_task(row) for row in rows]

            return tasks, total

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM tasks WHERE task_id = ?", (task_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    def _row_to_task(self, row) -> TranslationTask:
        """数据库行转任务对象"""
        return TranslationTask(
            task_id=row["task_id"],
            filename=row["filename"],
            status=TaskStatus(row["status"]),
            glossary_id=row["glossary_id"],
            bilingual=bool(row["bilingual"]) if "bilingual" in row.keys() else False,
            progress=TaskProgress(
                current=row["progress_current"],
                total=row["progress_total"],
                percentage=row["progress_percentage"],
                speed=row["progress_speed"],
                elapsed=row["progress_elapsed"]
            ),
            result_url=row["result_url"],
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        )
