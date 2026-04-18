"""
文件服务 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.pipelines.postprocess.export_service import ExportService
from ..database.db import Database
from ...domain.models.task_models import TaskStatus

router = APIRouter(prefix="/api/files", tags=["files"])
db = Database()


def _download_basename(filename: str) -> str:
    """生成稳定、可读的下载文件名前缀"""
    stem = Path(filename).stem.strip()
    return stem or "translation"


def _looks_bilingual_markdown(path: Path) -> bool:
    """粗略判断旧结果文件是否仍是双语 Markdown。"""
    if not path.exists():
        return False
    sample = path.read_text(encoding="utf-8")[:4000]
    return "（双语对照）" in sample or "\n> " in sample and "\n---" in sample


def _ensure_markdown_variants(task_id: str, bilingual_task: bool) -> tuple[Path, Path]:
    """
    确保单语/双语 Markdown 结果文件存在。
    对历史任务执行一次就地迁移：
    - 旧的 {task_id}.md 若是双语文件，会复制为 .bilingual.md
    - 再从双语内容提取出真正的单语 .md
    """
    mono_path = Path(f"data/results/{task_id}.md")
    bilingual_path = Path(f"data/results/{task_id}.bilingual.md")

    if bilingual_task:
        if bilingual_path.exists():
            source_bilingual = bilingual_path
        elif mono_path.exists() and _looks_bilingual_markdown(mono_path):
            legacy_content = mono_path.read_text(encoding="utf-8")
            bilingual_path.write_text(legacy_content, encoding="utf-8")
            mono_path.write_text(
                ExportService.strip_bilingual_markdown(legacy_content),
                encoding="utf-8",
            )
            source_bilingual = bilingual_path
        else:
            source_bilingual = bilingual_path

        if source_bilingual.exists():
            if (not mono_path.exists()) or _looks_bilingual_markdown(mono_path):
                mono_path.write_text(
                    ExportService.strip_bilingual_markdown(
                        source_bilingual.read_text(encoding="utf-8")
                    ),
                    encoding="utf-8",
                )

    elif not bilingual_task and not mono_path.exists() and bilingual_path.exists():
        mono_path.write_text(
            ExportService.strip_bilingual_markdown(
                bilingual_path.read_text(encoding="utf-8")
            ),
            encoding="utf-8",
        )

    return mono_path, bilingual_path


@router.get("/results/{task_id}")
async def download_result(
    task_id: str,
    format: str = Query("md", description="导出格式: md、html 或 zip"),
    variant: str = Query("mono", description="结果类型: mono 或 bilingual"),
):
    """
    下载翻译结果

    参数:
    - format: 导出格式 (md/html/zip)
    - variant: 结果类型 (mono/bilingual)

    返回: Markdown、HTML 或 ZIP 文件
    """
    if format not in {"md", "html", "zip"}:
        raise HTTPException(status_code=400, detail="不支持的导出格式")
    if variant not in {"mono", "bilingual"}:
        raise HTTPException(status_code=400, detail="不支持的结果类型")

    task = await db.get_task(task_id)
    if task and task.status not in {TaskStatus.COMPLETED, TaskStatus.PARTIAL_SUCCESS}:
        raise HTTPException(status_code=400, detail="任务尚未完成，无法下载结果")
    if task and variant == "bilingual" and not task.bilingual:
        raise HTTPException(status_code=400, detail="仅双语任务支持双语结果下载")

    base_name = _download_basename(task.filename) if task else f"translation_{task_id}"

    mono_path, bilingual_path = _ensure_markdown_variants(
        task_id=task_id,
        bilingual_task=bool(task.bilingual) if task else False,
    )

    result_path = bilingual_path if variant == "bilingual" else mono_path
    if not result_path.exists():
        if variant == "bilingual":
            legacy_path = Path(f"data/results/{task_id}.md")
            if legacy_path.exists():
                result_path = legacy_path
            else:
                raise HTTPException(status_code=404, detail="双语结果文件不存在")
        else:
            raise HTTPException(status_code=404, detail="结果文件不存在")

    if format == "html":
        if task and not task.bilingual:
            raise HTTPException(status_code=400, detail="仅双语任务支持 HTML 双栏导出")

        # 导出为 HTML 双栏格式
        html_path = Path(f"data/results/{task_id}.html")

        # 如果 HTML 不存在或 Markdown 更新了,重新生成
        if not html_path.exists() or html_path.stat().st_mtime < result_path.stat().st_mtime:
            ExportService.export_bilingual_html(
                str(result_path),
                str(html_path),
                title=f"翻译结果 - {task_id[:8]}"
            )

        return FileResponse(
            path=html_path,
            filename=f"{base_name}.bilingual.html",
            media_type="text/html"
        )

    if format == "zip":
        bundle_path = ExportService.create_assets_bundle(task_id=task_id)
        return FileResponse(
            path=bundle_path,
            filename=f"{base_name}.assets.zip",
            media_type="application/zip",
        )

    # 默认返回 Markdown
    return FileResponse(
        path=result_path,
        filename=f"{base_name}{'.bilingual' if variant == 'bilingual' else '.cn'}.md",
        media_type="text/markdown"
    )


@router.get("/uploads/{filename}")
async def get_upload_file(filename: str):
    """获取上传的原始文件"""
    file_path = Path(f"data/uploads/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(path=file_path)
