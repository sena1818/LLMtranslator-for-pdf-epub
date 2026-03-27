"""
文件服务 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.services.export_service import ExportService
from ..database.db import Database
from ..models.task import TaskStatus

router = APIRouter(prefix="/api/files", tags=["files"])
db = Database()


@router.get("/results/{task_id}")
async def download_result(
    task_id: str,
    format: str = Query("md", description="导出格式: md 或 html")
):
    """
    下载翻译结果

    参数:
    - format: 导出格式 (md/html)

    返回: Markdown 或 HTML 文件
    """
    result_path = Path(f"data/results/{task_id}.md")
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")

    if format == "html":
        task = await db.get_task(task_id)
        if task and not task.bilingual:
            raise HTTPException(status_code=400, detail="仅双语任务支持 HTML 双栏导出")
        if task and task.status not in {TaskStatus.COMPLETED, TaskStatus.PARTIAL_SUCCESS}:
            raise HTTPException(status_code=400, detail="任务尚未完成，无法导出 HTML")

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
            filename=f"translation_{task_id}.html",
            media_type="text/html"
        )

    # 默认返回 Markdown
    return FileResponse(
        path=result_path,
        filename=f"translation_{task_id}.md",
        media_type="text/markdown"
    )


@router.get("/uploads/{filename}")
async def get_upload_file(filename: str):
    """获取上传的原始文件"""
    file_path = Path(f"data/uploads/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(path=file_path)
