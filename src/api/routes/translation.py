"""
翻译任务 API 路由
"""
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from typing import Optional

from ..services.translation_service import TranslationService

router = APIRouter(prefix="/api/translation", tags=["translation"])
service = TranslationService()


@router.post("/tasks", status_code=201)
async def create_translation_task(
    file: UploadFile = File(...),
    glossary_id: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None
):
    """
    创建翻译任务

    请求:
    - file: 上传的文件 (PDF/EPUB/Markdown)
    - glossary_id: 术语表 ID (可选)

    返回:
    {
        "task_id": "uuid-string",
        "status": "pending",
        "filename": "book.md",
        "created_at": "2026-01-16T10:30:00"
    }
    """
    content = await file.read()
    task = await service.create_task(content, file.filename, glossary_id)

    # 后台启动翻译
    background_tasks.add_task(service.start_translation, task.task_id)

    return task.to_dict()


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态 (轮询端点)

    返回:
    {
        "task_id": "...",
        "status": "processing",
        "progress": {
            "current": 50,
            "total": 100,
            "percentage": 50.0,
            "speed": 12.5,
            "elapsed": 180
        },
        "result_url": null,
        "error": null
    }
    """
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.get("/tasks")
async def list_tasks(skip: int = 0, limit: int = 20):
    """
    获取任务列表

    返回:
    {
        "tasks": [...],
        "total": 100
    }
    """
    tasks, total = await service.list_tasks(skip, limit)
    return {"tasks": [t.to_dict() for t in tasks], "total": total}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务 (不可删除正在运行的任务)"""
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无法删除")
    return {"message": "删除成功"}
