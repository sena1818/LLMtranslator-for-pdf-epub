"""Prompt 模板库

把领域相关的翻译 Prompt 从引擎代码里外置到 prompts/{domain}.md，
便于在不改代码的前提下切换/微调不同体裁（哲学、文学、通用……）。
"""
from __future__ import annotations

from pathlib import Path


class PromptLibrary:
    """按领域加载翻译 Prompt 模板。"""

    def __init__(self, prompts_dir, default_domain: str = "philosophy"):
        self.prompts_dir = Path(prompts_dir)
        self.default_domain = default_domain

    def available_domains(self) -> list[str]:
        if not self.prompts_dir.exists():
            return []
        return sorted(p.stem for p in self.prompts_dir.glob("*.md"))

    def translator_template(self, domain: str | None = None) -> str:
        """返回指定领域的翻译模板文本；缺失则回退到默认领域。"""
        domain = domain or self.default_domain
        path = self.prompts_dir / f"{domain}.md"
        if not path.exists():
            path = self.prompts_dir / f"{self.default_domain}.md"
        return path.read_text(encoding="utf-8")
