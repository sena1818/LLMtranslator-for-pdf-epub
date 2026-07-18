from src.core.translator import DocumentProfile, TranslationEngine
from src.domain.rules.chunk_planning import TextChunk
from src.domain.rules.glossary_selection import select_relevant_glossary


def test_select_relevant_glossary_keeps_only_present_terms():
    glossary = {
        "Hyperstition": "超虚构 (Hyperstition)",
        "War Machine": "战争机器 (War Machine)",
        "Gradient Descent": "梯度下降 (Gradient Descent)",
    }
    selected = select_relevant_glossary(
        glossary, "The war machine drives hyperstition.", ""
    )
    assert set(selected) == {"Hyperstition", "War Machine"}


def test_select_relevant_glossary_is_case_insensitive_and_uses_context():
    glossary = {"Backpropagation": "反向传播 (Backpropagation)"}
    assert select_relevant_glossary(glossary, "no term here", "backpropagation appears") == glossary
    assert select_relevant_glossary(glossary, "", "") == {}
    assert select_relevant_glossary({}, "backpropagation") == {}


def _chunk(text: str) -> TextChunk:
    return TextChunk(
        index=0,
        chunk_id="chunk-0",
        text=text,
        section_path=["Section"],
        section_title="Section",
        context_text="",
    )


def test_cache_key_unaffected_by_unrelated_glossary_term():
    engine = TranslationEngine.__new__(TranslationEngine)
    engine.prompt_version = "v4"
    engine.document_profile = DocumentProfile(summary="profile-a")

    class Config:
        model_name = "test-model"
        prompt_fingerprint = "test-prompt-fingerprint"

    engine.config = Config()
    chunk = _chunk("Hyperstition accelerates myth.")

    engine.glossary = {"Hyperstition": "超虚构 (Hyperstition)"}
    key_before = TranslationEngine._build_cache_key(engine, chunk)

    # 新增一个本块不出现的术语，不应使该块缓存失效
    engine.glossary = {
        "Hyperstition": "超虚构 (Hyperstition)",
        "Gradient Descent": "梯度下降 (Gradient Descent)",
    }
    key_after = TranslationEngine._build_cache_key(engine, chunk)

    assert key_before == key_after


def test_cache_key_changes_when_relevant_term_changes():
    engine = TranslationEngine.__new__(TranslationEngine)
    engine.prompt_version = "v4"
    engine.document_profile = DocumentProfile(summary="profile-a")

    class Config:
        model_name = "test-model"
        prompt_fingerprint = "test-prompt-fingerprint"

    engine.config = Config()
    chunk = _chunk("Hyperstition accelerates myth.")

    engine.glossary = {"Hyperstition": "超虚构 (Hyperstition)"}
    key_before = TranslationEngine._build_cache_key(engine, chunk)

    engine.glossary = {"Hyperstition": "超虚拟"}
    key_after = TranslationEngine._build_cache_key(engine, chunk)

    assert key_before != key_after
