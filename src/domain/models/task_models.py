"""
任务领域模型
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    """任务进度"""

    current: int = 0
    total: int = 0
    percentage: float = 0.0
    speed: float = 0.0
    elapsed: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TranslationTask:
    """翻译任务领域对象"""

    task_id: str
    filename: str
    status: TaskStatus
    glossary_id: str | None = None
    bilingual: bool = False
    progress: TaskProgress | None = None
    result_url: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.progress is None:
            self.progress = TaskProgress()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "glossary_id": self.glossary_id,
            "bilingual": self.bilingual,
            "progress": self.progress.to_dict() if self.progress else {},
            "result_url": self.result_url,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
