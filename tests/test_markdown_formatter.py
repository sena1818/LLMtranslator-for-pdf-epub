from src.pipelines.postprocess.markdown_formatter import SmartMarkdownFormatter


def test_formatter_preserves_fence_and_converts_quote_div():
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

    assert "## Chapter One" in formatted
    assert "> Quoted line" in formatted
    assert '```python\nprint("hello")\n```' in formatted


def test_formatter_cleans_images_and_toc_div():
    formatter = SmartMarkdownFormatter()
    content = """::: tableofcontents
[Section](#section){.chaptertoc}
:::

![PIC](/tmp/book/images/page1.png){.calibre1}
"""

    formatted = formatter.format(content)

    assert "## 目录" in formatted
    assert "- [Section](#section)" in formatted
    assert "![page1](images/page1.png)" in formatted
