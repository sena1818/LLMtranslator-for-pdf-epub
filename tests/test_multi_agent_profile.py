from src.core.translator import DocumentProfile, TranslationEngine
from src.domain.rules.chunk_planning import TextChunk


def test_parse_document_profile():
    engine = TranslationEngine.__new__(TranslationEngine)

    class Config:
        analyst_max_term_hints = 3
        analyst_max_sections = 2

    engine.config = Config()
    profile = TranslationEngine._parse_document_profile(
        engine,
        """
        {
          "summary": "一本讨论超虚构与技术神话的文本。",
          "style_notes": ["保持学术张力", "避免口语化"],
          "terminology_hints": ["Hyperstition -> 超虚构 (Hyperstition)", "Warp -> 扭曲"],
          "section_overview": ["Introduction", "Circuitries", "Appendix"]
        }
        """,
    )

    assert profile.summary == "一本讨论超虚构与技术神话的文本。"
    assert profile.style_notes == ["保持学术张力", "避免口语化"]
    assert len(profile.terminology_hints) == 2
    assert profile.section_overview == ["Introduction", "Circuitries"]


def test_cache_key_changes_with_document_profile():
    engine = TranslationEngine.__new__(TranslationEngine)
    engine.prompt_version = "v3"
    engine.glossary = {"Hyperstition": "超虚构 (Hyperstition)"}

    class Config:
        model_name = "test-model"

    engine.config = Config()
    chunk = TextChunk(
        index=0,
        chunk_id="chunk-0",
        text="Hyperstition accelerates myth.",
        section_path=["Section"],
        section_title="Section",
        context_text="",
    )

    engine.document_profile = DocumentProfile(summary="profile-a")
    key_a = TranslationEngine._build_cache_key(engine, chunk)
    engine.document_profile = DocumentProfile(summary="profile-b")
    key_b = TranslationEngine._build_cache_key(engine, chunk)

    assert key_a != key_b
