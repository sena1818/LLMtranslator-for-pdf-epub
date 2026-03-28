import unittest

from src.services.markdown_formatter import SmartMarkdownFormatter


class SmartMarkdownFormatterTestCase(unittest.TestCase):
    def test_formatter_preserves_fence_and_converts_quote_div(self):
        formatter = SmartMarkdownFormatter()
        content = """## []{#sec .calibre1}Chapter One {.calibre2}

::: quote
Quoted line
:::

```python
print("hello")
```
"""

        formatted = formatter.format(content)

        self.assertIn("## Chapter One", formatted)
        self.assertIn("> Quoted line", formatted)
        self.assertIn("```python\nprint(\"hello\")\n```", formatted)

    def test_formatter_cleans_images_and_toc_div(self):
        formatter = SmartMarkdownFormatter()
        content = """::: tableofcontents
[Section](#section){.chaptertoc}
:::

![PIC](/tmp/book/images/page1.png){.calibre1}
"""

        formatted = formatter.format(content)

        self.assertIn("## 目录", formatted)
        self.assertIn("- [Section](#section)", formatted)
        self.assertIn("![page1](images/page1.png)", formatted)
