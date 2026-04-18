"""
兼容层：翻译任务数据模型

正式实现已迁移到 domain/models。
"""
from __future__ import annotations

from ...domain.models.task_models import TaskProgress, TaskStatus, TranslationTask

__all__ = ["TaskProgress", "TaskStatus", "TranslationTask"]
