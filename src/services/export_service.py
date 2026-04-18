"""
兼容层：导出服务

正式实现已迁移到 pipelines/postprocess。
"""
from __future__ import annotations

from ..pipelines.postprocess.export_service import BilingualParagraph, ExportService

__all__ = ["BilingualParagraph", "ExportService"]
