"""
术语表 API 路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ..services.glossary_service import GlossaryService
from ..models.glossary import (
    GlossaryCreateRequest,
    GlossaryUpdateRequest,
    GlossaryModifyRequest,
)

router = APIRouter(prefix="/api/glossary", tags=["glossary"])
service = GlossaryService()


@router.get("/")
async def list_glossaries():
    """
    获取术语表列表

    返回:
    [
        {
            "id": "cpglossary",
            "name": "Cpglossary",
            "term_count": 73,
            "updated_at": "2026-01-15T12:00:00"
        }
    ]
    """
    return await service.list_glossaries()


@router.get("/{glossary_id}")
async def get_glossary(glossary_id: str):
    """
    获取术语表内容

    返回:
    {
        "id": "cpglossary",
        "name": "Cpglossary",
        "terms": {
            "Hyperstition": "超虚构 (Hyperstition)"
        }
    }
    """
    glossary = await service.get_glossary(glossary_id)
    if not glossary:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return glossary


@router.post("/")
async def create_glossary(payload: GlossaryCreateRequest):
    """
    创建新术语表

    请求:
    {
        "name": "我的术语表",
        "terms": {"English": "中文"}
    }
    """
    return await service.create_glossary(payload.name, payload.terms)


@router.put("/{glossary_id}")
async def update_glossary(glossary_id: str, payload: GlossaryUpdateRequest):
    """
    更新术语表内容 (全量更新)

    请求:
    {
        "terms": {"English": "中文"}
    }
    """
    success = await service.update_glossary(glossary_id, payload.terms)
    if not success:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return {"message": "更新成功"}


@router.patch("/{glossary_id}/terms")
async def modify_terms(glossary_id: str, payload: GlossaryModifyRequest):
    """
    增量修改术语 (单个增删)

    请求:
    {
        "add": {"New Term": "新术语"},
        "remove": ["Old Term"]
    }
    """
    result = await service.modify_terms(glossary_id, payload.add, payload.remove)
    if result is None:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return {"message": "修改成功", "term_count": result}


@router.delete("/{glossary_id}")
async def delete_glossary(glossary_id: str):
    """删除术语表"""
    success = await service.delete_glossary(glossary_id)
    if not success:
        raise HTTPException(status_code=404, detail="术语表不存在")
    return {"message": "删除成功"}


@router.post("/import")
async def import_glossary(file: UploadFile = File(...), name: str = Form("")):
    """
    导入 JSON 术语表

    请求: multipart/form-data
    - file: JSON 文件
    - name: 术语表名称
    """
    if not name:
        name = file.filename.replace(".json", "")

    content = await file.read()
    glossary = await service.import_from_file(content, name)
    return glossary


@router.get("/{glossary_id}/export")
async def export_glossary(glossary_id: str):
    """
    导出术语表为 JSON

    返回: JSON 文件下载
    """
    from fastapi.responses import FileResponse

    file_path = await service.export_to_file(glossary_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="术语表不存在")

    return FileResponse(
        path=file_path,
        filename=f"{glossary_id}.json",
        media_type="application/json"
    )
