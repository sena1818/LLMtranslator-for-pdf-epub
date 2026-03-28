"""
EPUB / Pandoc 残留清理器

目标：
- 去除 Kindle / Calibre 的分页残留与空锚点
- 合并被拆开的图片类属性并修复图片路径
- 处理常见的 `[标题]{.calibreX}` 残留
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import yaml

from src.utils.config_loader import get_config


class EpubArtifactCleaner:
    """清理 EPUB 转 Markdown 后常见的结构残留"""

    def __init__(self):
        self.rule_sets = self._load_rules()
        self.rules = self._resolve_rules("epub")

    def clean(self, text: str, source_type: str = "epub") -> str:
        self.rules = self._resolve_rules(source_type)
        text = self._remove_pagebreak_blocks(text)
        text = self._remove_svg_wrapper_blocks(text)
        text = self._merge_multiline_image_attributes(text)
        text = self._normalize_escaped_list_markers(text)
        text = self._remove_anchor_lines(text)
        text = self._normalize_standalone_spans(text)
        text = self._normalize_standalone_bracket_lines(text)
        text = self._remove_orphan_class_lines(text)
        text = self._normalize_images(text)
        text = self._collapse_blank_lines(text)
        return text.strip() + "\n"

    def _load_rules(self) -> Dict[str, Any]:
        config = get_config()
        rules_path = config.artifact_rules_path
        if not rules_path.exists():
            return {}
        with open(rules_path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload

    def _resolve_rules(self, source_type: str) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        self._merge_rule_section(merged, self.rule_sets.get("common", {}))
        self._merge_source_rules(merged, source_type)
        return merged

    def _merge_source_rules(self, merged: Dict[str, Any], source_type: str):
        if not source_type:
            return
        section = self.rule_sets.get(source_type, {})
        for parent in section.get("inherit_from", []):
            self._merge_source_rules(merged, parent)
        self._merge_rule_section(merged, section)

    def _merge_rule_section(self, merged: Dict[str, Any], section: Dict[str, Any]):
        for key, value in section.items():
            if key == "inherit_from":
                continue
            if isinstance(value, list):
                merged.setdefault(key, [])
                merged[key].extend(value)
            elif isinstance(value, dict):
                merged.setdefault(key, {})
                merged[key].update(value)
            else:
                merged[key] = value

    def _remove_pagebreak_blocks(self, text: str) -> str:
        patterns = self.rules.get("strip_block_patterns") or [
            r"(?ms)^(?:>\s*)?:::\s*\{#[^}\n]*\.mbp_pagebreak[^}\n]*\}\s*\n(?:>\s*)?:::\s*\n?",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text)
        text = re.sub(
            r"(?m)^(?:>\s*)?:::\s*\{#[^}\n]*\.mbp_pagebreak[^}\n]*\}\s*$",
            "",
            text,
        )
        return text

    def _remove_svg_wrapper_blocks(self, text: str) -> str:
        pattern = re.compile(
            r"(?ms)^(?P<block>(?:>\s*)?:::\s*\{\}\s*\n(?:(?:>\s*)?.*\n)*?(?:>\s*)?:::\s*\n?)"
        )

        def replace(match: re.Match[str]) -> str:
            block = match.group("block")
            if "<svg" in block or "<image" in block:
                return ""
            return block

        return pattern.sub(replace, text)

    def _merge_multiline_image_attributes(self, text: str) -> str:
        return re.sub(
            r"((?:>\s*)?!\[[^\]]*\]\([^)]+\))\s*\n(?:>\s*)?\{[^}\n]+\}",
            r"\1",
            text,
        )

    def _remove_anchor_lines(self, text: str) -> str:
        patterns = self.rules.get("strip_line_patterns") or []
        for pattern in patterns:
            text = re.sub(pattern, "", text)
        text = re.sub(r"(?m)^(?:>\s*)?\[\]\{#[^}]+\}\s*$", "", text)
        return text

    def _normalize_escaped_list_markers(self, text: str) -> str:
        return re.sub(r"(?m)^(\s*(?:>\s*)?\d+)\\([.)])\s+", r"\1\2 ", text)

    def _normalize_standalone_spans(self, text: str) -> str:
        cleaned_lines = []
        for line in text.splitlines():
            quote_prefix, stripped = self._split_quote_prefix(line)
            match = re.match(r"^\[([^\]]*)\]\{\.([A-Za-z0-9_]+)\}$", stripped)
            if not match:
                malformed = re.match(r"^\[([^\]]*)\]\{\.([A-Za-z0-9_]+)\]$", stripped)
                if malformed:
                    content, class_name = malformed.groups()
                    content = content.replace("\u00a0", " ").strip()
                    if not content:
                        continue
                    if self._should_promote_to_heading(content, class_name):
                        cleaned_lines.append(
                            f"{quote_prefix}{self._heading_prefix(class_name)} {content}"
                        )
                    else:
                        cleaned_lines.append(f"{quote_prefix}{content}")
                    continue
                cleaned_lines.append(line)
                continue

            content, class_name = match.groups()
            content = content.replace("\u00a0", " ").strip()
            if not content:
                continue

            if self._should_promote_to_heading(content, class_name):
                cleaned_lines.append(
                    f"{quote_prefix}{self._heading_prefix(class_name)} {content}"
                )
            else:
                cleaned_lines.append(f"{quote_prefix}{content}")

        return "\n".join(cleaned_lines)

    def _normalize_standalone_bracket_lines(self, text: str) -> str:
        if not self.rules.get("unwrap_bracket_lines", True):
            return text

        max_length = int(self.rules.get("bracket_line_max_length", 80))
        cleaned_lines = []
        for line in text.splitlines():
            quote_prefix, stripped = self._split_quote_prefix(line)
            match = re.match(r"^\[([^\]]+)\]$", stripped)
            if not match:
                cleaned_lines.append(line)
                continue
            content = match.group(1).replace("\u00a0", " ").strip()
            if not content:
                continue
            if len(content) > max_length:
                cleaned_lines.append(line)
                continue
            cleaned_lines.append(f"{quote_prefix}{content}")
        return "\n".join(cleaned_lines)

    def _remove_orphan_class_lines(self, text: str) -> str:
        patterns = [
            r"(?m)^(?:>\s*)?\{\.?[A-Za-z0-9_\-]+\}\s*$",
            r"(?m)^(?:>\s*)?\]\{\.?[A-Za-z0-9_\-]+\}\s*$",
            r"(?m)^(?:>\s*)?\[\s*\]\{\.?[A-Za-z0-9_\-]+\}\s*$",
            r"(?m)^(?:>\s*)?\[[^\]]*\]\{\.?[A-Za-z0-9_\-]+\]\s*$",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text)
        return text

    def _normalize_images(self, text: str) -> str:
        def replace(match):
            alt = (match.group(1) or "").strip()
            path = match.group(2).strip()
            filename = Path(path).name
            lowered = path.lower()
            relative_path = f"images/{filename}" if "/images/" in lowered else filename
            if not alt or alt.upper() == "PIC":
                alt = Path(filename).stem
            return f"![{alt}]({relative_path})"

        return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace, text)

    def _collapse_blank_lines(self, text: str) -> str:
        text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)
        return text

    def _should_promote_to_heading(self, content: str, class_name: str) -> bool:
        if not class_name.startswith("calibre"):
            return False
        if len(content) > int(self.rules.get("heading_max_length", 60)):
            return False
        if re.search(r"[。！？.!?:：；;]$", content):
            return False
        if class_name in set((self.rules.get("heading_classes") or {}).keys()):
            return True
        return False

    def _heading_prefix(self, class_name: str) -> str:
        mapping = self.rules.get("heading_classes") or {
            "calibre2": "##",
            "calibre3": "###",
            "calibre4": "####",
            "calibre5": "####",
        }
        return mapping.get(class_name, "###")

    def _split_quote_prefix(self, line: str) -> tuple[str, str]:
        match = re.match(r"^(\s*>\s*)?(.*)$", line)
        if not match:
            return "", line.strip()
        prefix, body = match.groups()
        return prefix or "", body.strip()
