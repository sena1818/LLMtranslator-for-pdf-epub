"""翻译结果渲染器

把 TranslationResult 列表渲染为最终 Markdown。CLI 与 Web 共用同一套
渲染逻辑，避免单语/双语产物格式漂移，并消除此前散落三处的双语拼接代码。
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _header(filename: str, bilingual: bool) -> str:
    mode_text = "（双语对照）" if bilingual else ""
    return f"# {filename} - 中文翻译{mode_text}\n\n> 由 AI 自动翻译\n\n"


def _render_block(result, bilingual: bool) -> str:
    if result.success:
        if bilingual:
            quoted = "\n".join(
                f"> {line}" for line in result.original.strip().split("\n")
            )
            return f"{quoted}\n\n{result.translation}\n\n---"
        return result.translation

    # 失败块写入可读占位符，便于事后人工补全
    return (
        f"\n\n> **[翻译失败 - Chunk {result.chunk_index}]**\n"
        f"> *API 请求失败或超时,请根据以下原文手动补全:*\n\n"
        f"```text\n{result.original[:500]}...\n```\n\n"
    )


def render_results_markdown(results: Iterable, filename: str, bilingual: bool = False) -> str:
    """把翻译结果渲染为完整 Markdown 字符串。"""
    parts = [_header(filename, bilingual)]
    for result in sorted(results, key=lambda item: item.chunk_index):
        parts.append("\n\n")
        parts.append(_render_block(result, bilingual))
        parts.append("\n\n")
    return "".join(parts)


def write_results_markdown(output_path, filename: str, results, bilingual: bool = False) -> None:
    """渲染并写入文件。"""
    Path(output_path).write_text(
        render_results_markdown(results, filename, bilingual), encoding="utf-8"
    )
