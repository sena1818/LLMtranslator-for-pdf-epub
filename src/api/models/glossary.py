"""
术语表请求模型
"""

from pydantic import BaseModel, Field


class GlossaryCreateRequest(BaseModel):
    """创建术语表请求"""
    name: str
    terms: dict[str, str] = Field(default_factory=dict)


class GlossaryUpdateRequest(BaseModel):
    """全量更新术语表请求"""
    terms: dict[str, str]


class GlossaryModifyRequest(BaseModel):
    """增量修改术语请求"""
    add: dict[str, str] = Field(default_factory=dict)
    remove: list[str] = Field(default_factory=list)
