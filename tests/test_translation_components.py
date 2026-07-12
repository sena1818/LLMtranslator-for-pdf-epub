import asyncio

from langchain_core.runnables import RunnableLambda

from src.core.validator import QualityIssue, QualityReport, TranslationValidator
from src.domain.models.translation_models import DocumentProfile
from src.domain.rules.chunk_planning import TextChunk
from src.pipelines.translate.document_analyzer import DocumentAnalyzer
from src.pipelines.translate.prompt_builder import TranslationPromptBuilder
from src.pipelines.translate.quality_pipeline import TranslationQualityPipeline


def test_document_analyzer_parse():
    class Config:
        analyst_max_term_hints = 3
        analyst_max_sections = 2

    profile = DocumentAnalyzer.parse(
        """
        {
          "summary": "一本讨论超虚构与技术神话的文本。",
          "style_notes": ["保持学术张力", "避免口语化"],
          "terminology_hints": ["Hyperstition -> 超虚构 (Hyperstition)", "Warp -> 扭曲"],
          "section_overview": ["Introduction", "Circuitries", "Appendix"]
        }
        """,
        Config(),
    )

    assert profile.summary == "一本讨论超虚构与技术神话的文本。"
    assert profile.section_overview == ["Introduction", "Circuitries"]


def test_prompt_builder_contains_translation_contract():
    prompt = TranslationPromptBuilder().build_translation_prompt(
        TextChunk(
            index=0,
            chunk_id="chunk-0",
            text="Hyperstition accelerates myth.",
            section_path=["Section"],
            section_title="Section",
            context_text="",
        ),
        DocumentProfile(summary="test"),
    )
    rendered = prompt.format(
        document_profile="doc profile",
        glossary="- Hyperstition: 超虚构 (Hyperstition)",
        section_title="Section",
        context="ctx",
        text="body",
    )
    assert "完整保留所有 Markdown 格式" in rendered
    assert "核心术语表" in rendered


def test_quality_pipeline_repairs_via_checker():
    class Config:
        enable_qa_check = True
        max_fix_attempts = 1

    class DummyRateLimiter:
        async def acquire(self):
            return None

    async def dummy_checker(payload):
        return "修正后的译文"

    validator = TranslationValidator(untranslated_word_span=4, max_glossary_checks=10)
    pipeline = TranslationQualityPipeline(
        validator=validator,
        config=Config(),
        llm_checker=RunnableLambda(dummy_checker),
        prompt_builder=TranslationPromptBuilder(),
        rate_limiter=DummyRateLimiter(),
        clean_output=lambda text: text.strip(),
        glossary={"Hyperstition": "超虚构 (Hyperstition)"},
    )

    async def scenario():
        original_validate = validator.validate

        def fake_validate(original_text, translation, glossary):
            if translation == "原始坏译文":
                return QualityReport(
                    passed=False,
                    issues=[QualityIssue(kind="untranslated", severity="high", message="bad")],
                )
            return QualityReport(passed=True, issues=[])

        validator.validate = fake_validate
        try:
            return await pipeline.run(
                chunk=TextChunk(
                    index=0,
                    chunk_id="chunk-0",
                    text="Hyperstition accelerates myth.",
                    section_path=["Section"],
                    section_title="Section",
                    context_text="",
                ),
                translation="原始坏译文",
                document_profile=DocumentProfile(summary="profile"),
            )
        finally:
            validator.validate = original_validate

    translation, report, repaired = asyncio.run(scenario())
    assert translation == "修正后的译文"
    assert report.passed
    assert repaired
