"""
统一的结果后处理流水线

职责：
- Markdown 结构化格式化
- 资源同步
- 双语 HTML 导出
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from .export_service import ExportService
from .markdown_formatter import SmartMarkdownFormatter


class ResultPostprocessPipeline:
    """统一收敛结果文件的后处理操作。"""

    def __init__(self):
        self.formatter = SmartMarkdownFormatter()

    def format_markdown_file(self, markdown_path: Path, source_type: str = "epub") -> dict:
        """格式化 Markdown 结果文件并返回统计信息。"""
        content = markdown_path.read_text(encoding="utf-8")
        formatted = self.formatter.format(content, source_type=source_type)
        markdown_path.write_text(formatted, encoding="utf-8")
        return dict(self.formatter.stats)

    def sync_assets(
        self,
        markdown_paths: Iterable[Path | None],
        asset_sources: Iterable[Path],
        task_id: str,
    ) -> List[str]:
        """同步资源到结果目录。"""
        copied: List[str] = []
        normalized_sources = [Path(source) for source in asset_sources if Path(source).exists()]
        for markdown_path in markdown_paths:
            if markdown_path is None:
                continue
            if not markdown_path.exists():
                continue
            copied.extend(ExportService.sync_result_assets(
                markdown_path=markdown_path,
                asset_sources=normalized_sources,
                task_id=task_id,
            ) or [])
        return sorted(set(copied))

    def export_bilingual_html(
        self,
        markdown_path: Path,
        output_path: Optional[Path] = None,
        title: Optional[str] = None,
    ) -> Path:
        """导出双语 HTML。"""
        html_path = Path(
            ExportService.export_bilingual_html(
                markdown_path=str(markdown_path),
                output_path=str(output_path) if output_path else None,
                title=title,
            )
        )
        return html_path
