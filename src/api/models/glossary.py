"""
术语表请求模型
"""
from typing import Dict, List

from pydantic import BaseModel, Field


class GlossaryCreateRequest(BaseModel):
    """创建术语表请求"""
    name: str
    terms: Dict[str, str] = Field(default_factory=dict)


class GlossaryUpdateRequest(BaseModel):
    """全量更新术语表请求"""
    terms: Dict[str, str]


class GlossaryModifyRequest(BaseModel):
    """增量修改术语请求"""
    add: Dict[str, str] = Field(default_factory=dict)
    remove: List[str] = Field(default_factory=list)
