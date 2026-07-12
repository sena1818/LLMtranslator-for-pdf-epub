"""
SQLite 数据库管理
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from ...domain.models.task_models import TaskProgress, TaskStatus, TranslationTask

try:
    import aiosqlite
except ImportError:  # pragma: no cover - 允许轻量测试环境退化为 sqlite3
    aiosqlite = None


class Database:
    """SQLite 数据库管理"""

    def __init__(self, db_path: str = "data/translation.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect_sync(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    async def initialize(self):
        """初始化数据库表"""
        if aiosqlite is None:
            with self._connect_sync() as db:
                db.execute("""
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
                columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
                if "bilingual" not in columns:
                    db.execute("ALTER TABLE tasks ADD COLUMN bilingual INTEGER DEFAULT 0")
                db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
                    ON tasks(status, created_at)
                    """
                )
                db.commit()
            return

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

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
                ON tasks(status, created_at)
                """
            )

            await db.commit()

    async def save_task(self, task: TranslationTask):
        """保存任务"""
        if aiosqlite is None:
            with self._connect_sync() as db:
                db.execute("""
                    INSERT INTO tasks (
                        task_id, filename, status, glossary_id, bilingual,
                        progress_current, progress_total, progress_percentage,
                        progress_speed, progress_elapsed, result_url, error,
                        created_at, updated_at
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
                db.commit()
            return

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
        if aiosqlite is None:
            with self._connect_sync() as db:
                db.execute("""
                    UPDATE tasks SET
                        status = ?, bilingual = ?, progress_current = ?, progress_total = ?,
                        progress_percentage = ?, progress_speed = ?, progress_elapsed = ?,
                        result_url = ?, error = ?, updated_at = ?
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
                db.commit()
            return

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

    async def get_task(self, task_id: str) -> TranslationTask | None:
        """获取任务"""
        if aiosqlite is None:
            with self._connect_sync() as db:
                row = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                return self._row_to_task(row) if row else None

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()

                if not row:
                    return None

                return self._row_to_task(row)

    async def list_tasks(self, skip: int = 0, limit: int = 20) -> tuple[list[TranslationTask], int]:
        """获取任务列表"""
        if aiosqlite is None:
            with self._connect_sync() as db:
                total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                rows = db.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, skip)
                ).fetchall()
                tasks = [self._row_to_task(row) for row in rows]
                return tasks, total

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
        if aiosqlite is None:
            with self._connect_sync() as db:
                cursor = db.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                db.commit()
                return cursor.rowcount > 0

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM tasks WHERE task_id = ?", (task_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def claim_next_pending_task(self) -> TranslationTask | None:
        """原子认领下一个待处理任务"""
        if aiosqlite is None:
            with self._connect_sync() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT task_id FROM tasks
                    WHERE status = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (TaskStatus.PENDING.value,),
                ).fetchone()
                if not row:
                    db.commit()
                    return None
                now = datetime.now().isoformat()
                cursor = db.execute(
                    """
                    UPDATE tasks
                    SET status = ?, error = NULL, updated_at = ?
                    WHERE task_id = ? AND status = ?
                    """,
                    (TaskStatus.PROCESSING.value, now, row["task_id"], TaskStatus.PENDING.value),
                )
                if cursor.rowcount == 0:
                    db.commit()
                    return None
                claimed_row = db.execute(
                    "SELECT * FROM tasks WHERE task_id = ?",
                    (row["task_id"],),
                ).fetchone()
                db.commit()
                return self._row_to_task(claimed_row) if claimed_row else None

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")

            async with db.execute(
                """
                SELECT task_id
                FROM tasks
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (TaskStatus.PENDING.value,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                await db.commit()
                return None

            now = datetime.now().isoformat()
            update_cursor = await db.execute(
                """
                UPDATE tasks
                SET status = ?, error = NULL, updated_at = ?
                WHERE task_id = ? AND status = ?
                """,
                (
                    TaskStatus.PROCESSING.value,
                    now,
                    row["task_id"],
                    TaskStatus.PENDING.value,
                ),
            )

            if update_cursor.rowcount == 0:
                await db.commit()
                return None

            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (row["task_id"],),
            ) as cursor:
                claimed_row = await cursor.fetchone()

            await db.commit()
            return self._row_to_task(claimed_row) if claimed_row else None

    async def requeue_stale_processing_tasks(self, stale_after_seconds: int = 900) -> int:
        """将长时间未更新的 processing 任务重新放回队列"""
        stale_before = (datetime.now() - timedelta(seconds=stale_after_seconds)).isoformat()
        if aiosqlite is None:
            with self._connect_sync() as db:
                cursor = db.execute(
                    """
                    UPDATE tasks
                    SET status = ?, error = ?, updated_at = ?
                    WHERE status = ? AND updated_at IS NOT NULL AND updated_at < ?
                    """,
                    (
                        TaskStatus.PENDING.value,
                        "任务因 worker 中断被重新排队",
                        datetime.now().isoformat(),
                        TaskStatus.PROCESSING.value,
                        stale_before,
                    ),
                )
                db.commit()
                return cursor.rowcount

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE tasks
                SET status = ?, error = ?, updated_at = ?
                WHERE status = ? AND updated_at IS NOT NULL AND updated_at < ?
                """,
                (
                    TaskStatus.PENDING.value,
                    "任务因 worker 中断被重新排队",
                    datetime.now().isoformat(),
                    TaskStatus.PROCESSING.value,
                    stale_before,
                ),
            )
            await db.commit()
            return cursor.rowcount

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
