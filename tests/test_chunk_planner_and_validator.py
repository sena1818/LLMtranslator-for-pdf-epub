import unittest

from src.core.chunk_planner import ChunkPlanner
from src.core.validator import TranslationValidator


class ChunkPlannerTestCase(unittest.TestCase):
    def test_markdown_headings_drive_chunk_sections(self):
        planner = ChunkPlanner(chunk_size=80, context_window=40)
        text = """# Part One

Intro paragraph about theory.

## Subsection

This is a longer paragraph that should remain under the subsection title.

### Detail

Another paragraph.
"""

        chunks = planner.plan(text)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0].section_title, "Part One")
        self.assertEqual(chunks[1].section_title, "Subsection")
        self.assertIn("当前章节", chunks[1].context_text)
        self.assertTrue(chunks[0].chunk_id.startswith("chunk-0000-"))

    def test_short_chunks_are_merged_with_same_section(self):
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

        self.assertEqual(len(chunks), 1)
        self.assertIn("Short intro.", chunks[0].text)
        self.assertIn("Another short paragraph", chunks[0].text)


class TranslationValidatorTestCase(unittest.TestCase):
    def test_validator_flags_untranslated_and_terminology_issues(self):
        validator = TranslationValidator(untranslated_word_span=4, max_glossary_checks=10)
        original = "Hyperstition expands across the desert."
        translation = "Hyperstition expands across the desert."
        report = validator.validate(
            original_text=original,
            translation=translation,
            glossary={"Hyperstition": "超虚构 (Hyperstition)"},
        )

        self.assertFalse(report.passed)
        issue_kinds = {issue.kind for issue in report.issues}
        self.assertIn("untranslated", issue_kinds)
        self.assertIn("terminology", issue_kinds)
