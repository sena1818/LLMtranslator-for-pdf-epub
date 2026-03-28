"""
翻译缓存

基于 SQLite 持久化成功的 chunk 翻译结果，
用于断点式恢复与重复翻译跳过。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import aiosqlite


@dataclass
class CacheEntry:
    """缓存命中结果"""

    cache_key: str
    chunk_id: str
    translation: str
    quality_report: dict
    repaired: bool


class TranslationCache:
    """基于 SQLite 的 chunk 翻译缓存"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """初始化缓存表"""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS translation_cache (
                    cache_key TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    quality_report TEXT,
                    repaired INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

        self._initialized = True

    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        """读取缓存"""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM translation_cache WHERE cache_key = ?",
                (cache_key,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return None

        return CacheEntry(
            cache_key=row["cache_key"],
            chunk_id=row["chunk_id"],
            translation=row["translation"],
            quality_report=json.loads(row["quality_report"] or "{}"),
            repaired=bool(row["repaired"]),
        )

    async def set(
        self,
        cache_key: str,
        chunk_id: str,
        translation: str,
        quality_report: dict,
        repaired: bool,
    ):
        """写入缓存"""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO translation_cache (
                    cache_key,
                    chunk_id,
                    translation,
                    quality_report,
                    repaired,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    chunk_id,
                    translation,
                    json.dumps(quality_report, ensure_ascii=False),
                    int(repaired),
                    datetime.now(UTC).isoformat(),
                ),
            )
            await db.commit()
