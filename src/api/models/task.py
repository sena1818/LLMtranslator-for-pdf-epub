"""
翻译任务数据模型
"""
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskProgress:
    """任务进度"""
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    speed: float = 0.0  # chunks/分钟
    elapsed: float = 0.0  # 秒

    def to_dict(self):
        return asdict(self)


@dataclass
class TranslationTask:
    """翻译任务"""
    task_id: str
    filename: str
    status: TaskStatus
    glossary_id: Optional[str] = None
    progress: TaskProgress = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.progress is None:
            self.progress = TaskProgress()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "glossary_id": self.glossary_id,
            "progress": self.progress.to_dict() if self.progress else {},
            "result_url": self.result_url,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
