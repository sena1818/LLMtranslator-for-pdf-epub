from src.core.validator import TranslationValidator
from src.domain.rules.chunk_planning import ChunkPlanner


def test_markdown_headings_drive_chunk_sections():
    planner = ChunkPlanner(chunk_size=80, context_window=40)
    text = """# Part One

Intro paragraph about theory.

## Subsection

This is a longer paragraph that should remain under the subsection title.

### Detail

Another paragraph.
"""

    chunks = planner.plan(text)

    assert len(chunks) >= 3
    assert chunks[0].section_title == "Part One"
    assert chunks[1].section_title == "Subsection"
    assert "当前章节" in chunks[1].context_text
    assert chunks[0].chunk_id.startswith("chunk-0000-")


def test_short_chunks_are_merged_with_same_section():
    planner = ChunkPlanner(
        chunk_size=120,
        target_chunk_size=100,
        min_chunk_size=50,
        context_window=40,
    )
    text = """# Section

Short intro.

Another short paragraph that should be merged into the same chunk.

Final remark.
"""

    chunks = planner.plan(text)

    assert len(chunks) == 1
    assert "Short intro." in chunks[0].text
    assert "Another short paragraph" in chunks[0].text


def test_validator_flags_untranslated_and_terminology_issues():
    validator = TranslationValidator(untranslated_word_span=4, max_glossary_checks=10)
    original = "Hyperstition expands across the desert."
    translation = "Hyperstition expands across the desert."
    report = validator.validate(
        original_text=original,
        translation=translation,
        glossary={"Hyperstition": "超虚构 (Hyperstition)"},
    )

    assert not report.passed
    issue_kinds = {issue.kind for issue in report.issues}
    assert "untranslated" in issue_kinds
    assert "terminology" in issue_kinds
