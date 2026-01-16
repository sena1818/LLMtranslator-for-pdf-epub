"""
文件服务 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/results/{task_id}")
async def download_result(task_id: str):
    """
    下载翻译结果

    返回: Markdown 文件
    """
    result_path = Path(f"data/results/{task_id}.md")
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")

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
