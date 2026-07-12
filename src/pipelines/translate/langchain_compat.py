"""
LangChain 兼容层

让轻量测试环境在缺少 langchain 时仍能导入模块与运行最小测试。
生产环境会优先使用真实 LangChain 类。
"""
from __future__ import annotations

try:
    from langchain_core.output_parsers import StrOutputParser as _StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate as _ChatPromptTemplate

    ChatPromptTemplate = _ChatPromptTemplate
    StrOutputParser = _StrOutputParser
    HAS_LANGCHAIN = True
except ImportError:  # pragma: no cover - 仅在瘦测试环境下生效
    HAS_LANGCHAIN = False

    class _RenderedPrompt:
        def __init__(self, text: str):
            self.text = text

        def to_string(self) -> str:
            return self.text

        def __str__(self) -> str:
            return self.text

    class ChatPromptTemplate:
        def __init__(self, template: str):
            self.template = template

        @classmethod
        def from_template(cls, template: str) -> ChatPromptTemplate:
            return cls(template)

        def format(self, **kwargs) -> str:
            return self.template.format(**kwargs)

        def format_prompt(self, **kwargs) -> _RenderedPrompt:
            return _RenderedPrompt(self.format(**kwargs))

        def __or__(self, other):
            return _FallbackChain([self, other])

    class StrOutputParser:
        def __or__(self, other):
            return _FallbackChain([self, other])

    class _FallbackChain:
        def __init__(self, parts):
            self.parts = parts

        def __or__(self, other):
            return _FallbackChain(self.parts + [other])

        async def ainvoke(self, payload):
            value = payload
            for part in self.parts:
                if isinstance(part, ChatPromptTemplate):
                    value = part.format(**payload)
                elif hasattr(part, "ainvoke"):
                    value = await part.ainvoke(value)
                else:
                    value = value
            return value
