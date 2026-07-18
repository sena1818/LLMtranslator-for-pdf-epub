"""
翻译 Prompt 构造器

角色与要求默认面向通用专业文本；可通过配置文件的 prompt: 段按领域覆盖
（translator_role / translation_requirements / repair_role /
repair_requirements / analyst_requirements），参见 config/research_paper.yaml。
"""
from __future__ import annotations

from ...core.chunk_planner import TextChunk
from ...domain.models.translation_models import DocumentProfile
from .langchain_compat import ChatPromptTemplate

DEFAULT_TRANSLATOR_ROLE = (
    "你是资深的专业文本译者，擅长在术语表约束下翻译术语密集的各领域专业文本"
    "（哲学、机器学习、科研论文、技术文档等）。"
)

DEFAULT_TRANSLATION_REQUIREMENTS = [
    "完整保留所有 Markdown 格式（标题、加粗、图片、链接、代码块）",
    "风格：忠实原文文体与论证强度，术语准确、行文严谨",
    "专有名词首次出现时保留英文原文在括号内",
    "严格使用术语表中的译名",
    "直接输出译文，不要任何前言、解释、注释",
]

DEFAULT_REPAIR_ROLE = "你是专业文本翻译审校者。请在不改变原意和 Markdown 结构的前提下修正译文。"

DEFAULT_REPAIR_REQUIREMENTS = [
    "只修正问题相关部分",
    "保留标题、链接、图片、代码块、引用块",
    "不要添加说明或注释",
    "直接输出修正后的完整译文",
]

DEFAULT_ANALYST_REQUIREMENTS = [
    "不要输出 JSON 以外的任何文字",
    "style_notes 最多 4 条",
    "terminology_hints 最多 {max_term_hints} 条",
    "section_overview 只保留最关键的章节线索",
]


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


class TranslationPromptBuilder:
    """统一生成翻译与审校 Prompt。

    注意：要求条目会直接进入 ChatPromptTemplate，除 analyst_requirements 中的
    {max_term_hints} 占位符外，配置文本中不要使用花括号。
    """

    def __init__(self, config=None):
        def _get(key: str, default):
            value = config.get(key) if config is not None else None
            return value if value else default

        self.translator_role = _get("prompt.translator_role", DEFAULT_TRANSLATOR_ROLE)
        self.translation_requirements = _get(
            "prompt.translation_requirements", DEFAULT_TRANSLATION_REQUIREMENTS
        )
        self.repair_role = _get("prompt.repair_role", DEFAULT_REPAIR_ROLE)
        self.repair_requirements = _get(
            "prompt.repair_requirements", DEFAULT_REPAIR_REQUIREMENTS
        )
        self.analyst_requirements = _get(
            "prompt.analyst_requirements", DEFAULT_ANALYST_REQUIREMENTS
        )

    def build_translation_prompt(
        self,
        chunk: TextChunk,
        document_profile: DocumentProfile | None = None,
    ) -> ChatPromptTemplate:
        template = f"""{self.translator_role}

【文档分析员备忘】:
{{document_profile}}

【核心术语表】(必须严格遵守):
{{glossary}}

【当前章节】:
{{section_title}}

【上文语境】:
{{context}}

【待翻译文本】:
{{text}}

---
【翻译要求】:
{_numbered(self.translation_requirements)}

开始翻译:
"""
        return ChatPromptTemplate.from_template(template)

    def build_repair_prompt(self) -> ChatPromptTemplate:
        template = f"""{self.repair_role}

【章节】:
{{section_title}}

【原文】:
{{original}}

【当前译文】:
{{translation}}

【发现的问题】:
{{issues}}

【文档分析员备忘】:
{{document_profile}}

【术语表】(必须严格遵守):
{{glossary}}

---
要求：
{_numbered(self.repair_requirements)}
"""
        return ChatPromptTemplate.from_template(template)

    def build_analyst_prompt(self) -> ChatPromptTemplate:
        template = f"""你是翻译团队中的“文档分析员”。请基于以下文档片段和章节信息，为后续翻译提供全局指导。

输出必须是 JSON 对象，格式如下：
{{{{
  "summary": "一句到三句的文档摘要",
  "style_notes": ["风格提示1", "风格提示2"],
  "terminology_hints": ["术语提示1", "术语提示2"],
  "section_overview": ["章节1", "章节2"]
}}}}

要求：
{_numbered(self.analyst_requirements)}

【章节列表】:
{{sections}}

【文档片段】:
{{excerpt}}
"""
        return ChatPromptTemplate.from_template(template)
