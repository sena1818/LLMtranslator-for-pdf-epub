"""stdio MCP 接口：把翻译系统暴露为可被 MCP 客户端编排的能力节点。

延迟导入 server，避免 `python -m src.interfaces.mcp.server` 时因包初始化
提前导入子模块而触发 RuntimeWarning。
"""
from __future__ import annotations

__all__ = ["TranslatorMCPServer", "build_server"]


def __getattr__(name: str):
    if name in __all__:
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
