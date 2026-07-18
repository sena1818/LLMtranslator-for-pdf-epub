import asyncio

from langchain_core.runnables import RunnableLambda

from src.pipelines.glossary.glossary_extractor import (
    GlossaryCandidate,
    GlossaryExtractor,
    candidates_to_glossary,
)
from src.pipelines.translate.prompt_builder import TranslationPromptBuilder


def test_parse_dedups_and_skips_existing():
    raw = """
    {
      "terms": [
        {"term": "Gradient Descent", "translation": "梯度下降 (Gradient Descent)", "note": "优化算法"},
        {"term": "gradient descent", "translation": "梯度下降", "note": "重复项"},
        {"term": "Hyperstition", "translation": "超虚构 (Hyperstition)", "note": "已有"},
        {"term": "", "translation": "空术语", "note": ""},
        {"term": "Backpropagation", "translation": "反向传播 (Backpropagation)", "note": ""}
      ]
    }
    """
    candidates = GlossaryExtractor.parse(
        raw, existing_glossary={"Hyperstition": "超虚构 (Hyperstition)"}
    )
    terms = [c.term for c in candidates]
    assert terms == ["Gradient Descent", "Backpropagation"]
    assert candidates[0].note == "优化算法"


def test_parse_extracts_json_from_noisy_output():
    raw = "```json\n{\"terms\": [{\"term\": \"Warp\", \"translation\": \"扭曲 (Warp)\"}]}\n```"
    candidates = GlossaryExtractor.parse(raw)
    assert len(candidates) == 1
    assert candidates[0].term == "Warp"


def test_parse_returns_empty_on_garbage():
    assert GlossaryExtractor.parse("not json at all") == []


def test_parse_respects_max_terms():
    raw = '{"terms": [{"term": "A", "translation": "a"}, {"term": "B", "translation": "b"}]}'
    assert len(GlossaryExtractor.parse(raw, max_terms=1)) == 1


def test_candidates_to_glossary():
    candidates = [
        GlossaryCandidate(term="Warp", translation="扭曲 (Warp)", note="x"),
        GlossaryCandidate(term="Flux", translation="流变 (Flux)"),
    ]
    assert candidates_to_glossary(candidates) == {
        "Warp": "扭曲 (Warp)",
        "Flux": "流变 (Flux)",
    }


def test_extract_end_to_end_with_fake_llm():
    class Config:
        glossary_extraction_max_chars = 16000
        glossary_extraction_max_terms = 60

        def get(self, key, default=None):
            return default

    captured = {}

    async def fake_llm(prompt_value):
        captured["prompt"] = prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
        return '{"terms": [{"term": "Hyperstition", "translation": "超虚构 (Hyperstition)", "note": "核心概念"}]}'

    extractor = GlossaryExtractor(
        llm=RunnableLambda(fake_llm),
        config=Config(),
        prompt_builder=TranslationPromptBuilder(Config()),
    )

    candidates = asyncio.run(
        extractor.extract("Hyperstition drives the text.", existing_glossary={})
    )
    assert len(candidates) == 1
    assert candidates[0].term == "Hyperstition"
    # existing_terms 与文档片段应进入 prompt
    assert "Hyperstition drives the text." in captured["prompt"]
