import unittest

from src.services.epub_artifact_cleaner import EpubArtifactCleaner
from src.services.markdown_formatter import SmartMarkdownFormatter


class EpubArtifactCleanerTestCase(unittest.TestCase):
    def test_cleaner_removes_pagebreaks_and_normalizes_spans_and_images(self):
        cleaner = EpubArtifactCleaner()
        content = """::: {#index_split_002.html_calibre_pb_2 .mbp_pagebreak}
:::

[第一篇章]{.calibre2}
[同一（性）]{.calibre2}

![](data/temp/task/images/images/00005.jpg)
{.calibre_2}

[]{#index_split_003.html}
"""

        cleaned = cleaner.clean(content)

        self.assertNotIn("mbp_pagebreak", cleaned)
        self.assertNotIn("[]{#index_split_003.html}", cleaned)
        self.assertIn("## 第一篇章", cleaned)
        self.assertIn("## 同一（性）", cleaned)
        self.assertIn("![00005](images/00005.jpg)", cleaned)

    def test_cleaner_handles_bilingual_quote_artifacts(self):
        cleaner = EpubArtifactCleaner()
        content = r"""> ::: {#index_split_002.html_calibre_pb_2 .mbp_pagebreak}
> :::
>
> [Foreword]
>
> [ ]
>
> ![](data/temp/task/images/images/00005.jpg)
> {.calibre_2}
>
> 1\) First item
>
> <svg xmlns="http://www.w3.org/2000/svg">
> `<image width="801" height="1186" xlink:href="images/calibre_cover.jpg">`{=html}`</image>`{=html}
> </svg>
"""

        cleaned = cleaner.clean(content)

        self.assertNotIn("mbp_pagebreak", cleaned)
        self.assertNotIn("[\u00a0]", cleaned)
        self.assertNotIn("<svg", cleaned)
        self.assertIn("> Foreword", cleaned)
        self.assertIn("> ![00005](images/00005.jpg)", cleaned)
        self.assertIn("> 1) First item", cleaned)

    def test_formatter_cleans_epub_residue_end_to_end(self):
        formatter = SmartMarkdownFormatter()
        content = """::: {#index_split_002.html_calibre_pb_2 .mbp_pagebreak}
:::

[第一篇章]{.calibre2}

![](data/temp/task/images/images/00005.jpg)
{.calibre_2}
"""

        formatted = formatter.format(content)

        self.assertNotIn("mbp_pagebreak", formatted)
        self.assertIn("## 第一篇章", formatted)
        self.assertIn("![00005](images/00005.jpg)", formatted)

    def test_cleaner_supports_source_specific_rules(self):
        cleaner = EpubArtifactCleaner()
        content = """[]{#kindlepos123}
[]{#filepos456}
[Chapter One]{.calibre3}
"""

        cleaned = cleaner.clean(content, source_type="kindle")

        self.assertNotIn("kindlepos", cleaned)
        self.assertNotIn("filepos", cleaned)
        self.assertIn("### Chapter One", cleaned)
