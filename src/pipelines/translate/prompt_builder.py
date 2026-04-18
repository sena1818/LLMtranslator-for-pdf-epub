"""
翻译 Prompt 构造器
"""
from __future__ import annotations

from ...core.chunk_planner import TextChunk
from ...domain.models.translation_models import DocumentProfile
from .langchain_compat import ChatPromptTemplate


class TranslationPromptBuilder:
    """统一生成翻译与审校 Prompt。"""

    def build_translation_prompt(
        self,
        chunk: TextChunk,
        document_profile: DocumentProfile | None = None,
    ) -> ChatPromptTemplate:
        profile = document_profile or DocumentProfile.empty()
        template = """你是专业的后现代哲学翻译家,正在翻译学术文本。

【文档分析员备忘】:
{document_profile}

【核心术语表】(必须严格遵守):
{glossary}

【当前章节】:
{section_title}

【上文语境】:
{context}

【待翻译文本】:
{text}

---
【翻译要求】:
1. 完整保留所有 Markdown 格式（标题、加粗、图片、链接、代码块）
2. 风格：学术、精确、保持理论张力
3. 专有名词首次出现时保留英文原文在括号内
4. 严格使用术语表中的译名
5. 直接输出译文，不要任何前言、解释、注释

开始翻译:
"""
        return ChatPromptTemplate.from_template(template)

    def build_repair_prompt(self) -> ChatPromptTemplate:
        template = """你是学术翻译审校者。请在不改变原意和 Markdown 结构的前提下修正译文。

【章节】:
{section_title}

【原文】:
{original}

【当前译文】:
{translation}

【发现的问题】:
{issues}

【文档分析员备忘】:
{document_profile}

【术语表】(必须严格遵守):
{glossary}

---
要求：
1. 只修正问题相关部分
2. 保留标题、链接、图片、代码块、引用块
3. 不要添加说明或注释
4. 直接输出修正后的完整译文
"""
        return ChatPromptTemplate.from_template(template)

    def build_analyst_prompt(self) -> ChatPromptTemplate:
        template = """你是翻译团队中的“文档分析员”。请基于以下文档片段和章节信息，为后续翻译提供全局指导。

输出必须是 JSON 对象，格式如下：
{{
  "summary": "一句到三句的文档摘要",
  "style_notes": ["风格提示1", "风格提示2"],
  "terminology_hints": ["术语提示1", "术语提示2"],
  "section_overview": ["章节1", "章节2"]
}}

要求：
1. 不要输出 JSON 以外的任何文字
2. style_notes 最多 4 条
3. terminology_hints 最多 {max_term_hints} 条
4. section_overview 只保留最关键的章节线索

【章节列表】:
{sections}

【文档片段】:
{excerpt}
"""
        return ChatPromptTemplate.from_template(template)
