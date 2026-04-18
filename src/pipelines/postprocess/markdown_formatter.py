"""
结构化 Markdown 格式化器

以块级节点为核心处理标题、代码块、Pandoc div、列表和段落，
避免纯全局正则替换对复杂 Markdown 结构造成误伤。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from ..preprocess.artifact_cleaner import EpubArtifactCleaner


@dataclass
class BlockNode:
    """块级节点"""

    kind: str
    lines: List[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class SmartMarkdownFormatter:
    """结构化 Markdown 格式化器"""

    def __init__(self):
        self.artifact_cleaner = EpubArtifactCleaner()
        self.stats = {
            "headers_normalized": 0,
            "quotes_converted": 0,
            "emphasis_converted": 0,
            "anchors_removed": 0,
            "html_cleaned": 0,
            "toc_preserved": 0,
            "images_fixed": 0,
            "code_blocks_preserved": 0,
            "book_formatting_enhanced": 0,
        }

    def format(self, text: str, source_type: str = "epub") -> str:
        """执行结构化格式化"""
        text = self.artifact_cleaner.clean(text, source_type=source_type)
        nodes = self.parse_blocks(text)
        rendered = self.render_blocks(nodes)
        rendered = self.normalize_whitespace(rendered)
        self.stats["book_formatting_enhanced"] = 1
        return rendered.strip() + "\n"

    def parse_blocks(self, text: str) -> List[BlockNode]:
        """将 Markdown 文本解析为块级节点"""
        lines = text.splitlines()
        nodes: List[BlockNode] = []
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if re.match(r"^```", stripped):
                node, index = self._consume_fence(lines, index)
                nodes.append(node)
                continue

            if re.match(r"^:::\s*", stripped):
                node, index = self._consume_div(lines, index)
                nodes.append(node)
                continue

            if stripped == "":
                nodes.append(BlockNode(kind="blank"))
                index += 1
                continue

            if re.match(r"^#{1,6}\s*", stripped):
                nodes.append(BlockNode(kind="header", lines=[line]))
                index += 1
                continue

            if self._is_list_item(stripped):
                node, index = self._consume_list(lines, index)
                nodes.append(node)
                continue

            node, index = self._consume_paragraph(lines, index)
            nodes.append(node)

        return nodes

    def render_blocks(self, nodes: List[BlockNode]) -> str:
        """将节点重新渲染为 Markdown"""
        rendered_nodes: List[str] = []

        for node in nodes:
            if node.kind == "blank":
                rendered_nodes.append("")
                continue

            if node.kind == "fence":
                self.stats["code_blocks_preserved"] += 1
                rendered_nodes.append("\n".join(node.lines))
                continue

            if node.kind == "header":
                header = self.normalize_header(node.lines[0])
                if header:
                    rendered_nodes.extend(self._append_with_padding(rendered_nodes, header))
                continue

            if node.kind == "div":
                rendered = self.render_div(node)
                if rendered:
                    rendered_nodes.extend(self._append_with_padding(rendered_nodes, rendered))
                continue

            if node.kind == "list":
                rendered_nodes.append(self.render_list(node))
                continue

            if node.kind == "paragraph":
                rendered_nodes.append(self.clean_inline("\n".join(node.lines)))

        return "\n".join(rendered_nodes)

    def render_div(self, node: BlockNode) -> str:
        """渲染 Pandoc div 节点"""
        div_type = node.meta.get("div_type", "")
        body = "\n".join(node.lines).strip()
        if not body:
            return ""

        if div_type in {"quote", "center", "block"}:
            self.stats["quotes_converted"] += 1
            quote_lines = []
            for line in body.splitlines():
                cleaned = self.clean_inline(line)
                quote_lines.append(f"> {cleaned}" if cleaned else ">")
            return "\n".join(quote_lines)

        if div_type in {"tableofcontents", "toc"}:
            self.stats["toc_preserved"] += 1
            cleaned = self._clean_toc_lines(node.lines)
            parts = ["## 目录"]
            if cleaned:
                parts.extend(cleaned)
            return "\n".join(parts)

        inner_nodes = self.parse_blocks(body)
        return self.render_blocks(inner_nodes)

    def render_list(self, node: BlockNode) -> str:
        """渲染列表节点"""
        return "\n".join(self.clean_inline(line) for line in node.lines)

    def normalize_header(self, line: str) -> str:
        """清理标题里的 Pandoc/Calibre 残留"""
        match = re.match(r"^(#{1,6})\s*(.*)$", line.strip())
        if not match:
            return self.clean_inline(line)

        level, rest = match.groups()
        rest = re.sub(r"\[\]\{[^}]+\}", "", rest)
        rest = re.sub(r"\[([^\]]+)\]\{[^}]+\}", r"\1", rest)
        rest = re.sub(r"\{[^}]+\}", "", rest)
        rest = self.clean_inline(rest).strip()
        if not rest:
            return ""
        self.stats["headers_normalized"] += 1
        return f"{level} {rest}"

    def clean_inline(self, text: str) -> str:
        """清理非代码块的内联标记"""
        segments = re.split(r"(`[^`\n]+`)", text)
        cleaned_segments: List[str] = []

        for segment in segments:
            if not segment:
                continue
            if segment.startswith("`") and segment.endswith("`"):
                cleaned_segments.append(segment)
                continue
            cleaned_segments.append(self._clean_non_code_segment(segment))

        return "".join(cleaned_segments)

    def _clean_non_code_segment(self, text: str) -> str:
        count_before = len(text)
        text = re.sub(r"`<!--.*?-->`\{=html\}", "", text)
        text = re.sub(r"<!--.*?-->", "", text)
        if len(text) != count_before:
            self.stats["html_cleaned"] += 1

        anchor_patterns = [
            r"\[\]\{#[^}]+\}",
            r"\{#[A-Za-z0-9_\-\.]+\}",
            r"\[\]\{\.image[^}]*\}",
        ]
        for pattern in anchor_patterns:
            matches = len(re.findall(pattern, text))
            if matches:
                self.stats["anchors_removed"] += matches
                text = re.sub(pattern, "", text)

        text = re.sub(r"\[([^\]]+)\]\{\.emphasis\}", r"**\1**", text)
        text = re.sub(r"\[([^\]]+)\]\{\.italic\}", r"*\1*", text)
        text = re.sub(r"\[([^\]]*)\]\{\.([A-Za-z0-9_]+)\]", r"\1", text)
        self.stats["emphasis_converted"] += text.count("**") + text.count("*")

        text = self._clean_images(text)
        text = self._clean_links(text)

        text = re.sub(r"\{style=\"[^\"]*\"\}", "", text)
        text = re.sub(
            r"\{(?:\.[A-Za-z0-9_-]+(?:\s+\.[A-Za-z0-9_-]+)*)\}",
            "",
            text,
        )
        text = re.sub(r"\[([^\]]+)\]\{[^}]+\}", r"\1", text)
        text = re.sub(r"\\\s*\n", "\n", text)
        return text.strip()

    def _clean_images(self, text: str) -> str:
        def fix_image(match):
            alt = match.group(1) or ""
            path = match.group(2)
            filename = Path(path).name

            if "images/" in path:
                relative_path = "images/" + filename
            else:
                relative_path = filename

            if alt.upper() == "PIC" or not alt:
                alt = Path(filename).stem

            self.stats["images_fixed"] += 1
            return f"![{alt}]({relative_path})"

        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)\{[^}]*\}", fix_image, text)
        text = re.sub(
            r"!\[PIC\]\(([^)]+)\)",
            lambda match: f"![{Path(match.group(1)).stem}]({match.group(1)})",
            text,
        )
        return text

    def _clean_links(self, text: str) -> str:
        text = re.sub(r"\[\s*\[([^\]]+)\]\(([^)]+)\)\s*\]\{[^}]+\}", r"[\1](\2)", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)\{[^}]+\}", r"[\1](\2)", text)
        return text

    def _clean_toc_lines(self, lines: List[str]) -> List[str]:
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped in {":::", "::: tableofcontents"}:
                continue

            line = self.clean_inline(line)
            if re.search(r"\[[^\]]+\]\((#[^)]+)\)", line):
                if stripped.startswith("-") or stripped.startswith("*"):
                    cleaned.append(line)
                else:
                    cleaned.append(f"- {line.strip()}")
                continue

            cleaned.append(line)

        return cleaned

    def normalize_whitespace(self, text: str) -> str:
        """标准化空白与段落间距"""
        text = re.sub(r"(?m)^(\s*\d+)\\([.)])\s+", r"\1\2 ", text)
        text = re.sub(r"\n\n\n+", "\n\n", text)
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        return text

    def print_stats(self):
        """打印格式化统计"""
        print("\n📊 格式化统计:")
        print(f"  - 目录保留: {self.stats['toc_preserved']}")
        print(f"  - 标题标准化: {self.stats['headers_normalized']}")
        print(f"  - 引用块转换: {self.stats['quotes_converted']}")
        print(f"  - 强调格式转换: {self.stats['emphasis_converted']}")
        print(f"  - 图片修复: {self.stats['images_fixed']}")
        print(f"  - 锚点移除: {self.stats['anchors_removed']}")
        print(f"  - HTML清理: {self.stats['html_cleaned']}")
        print(f"  - 代码块保留: {self.stats['code_blocks_preserved']}")
        print(f"  - 书籍排版优化: {'是' if self.stats['book_formatting_enhanced'] else '否'}")

    def _append_with_padding(self, rendered_nodes: List[str], block_text: str) -> List[str]:
        parts: List[str] = []
        if rendered_nodes and rendered_nodes[-1] != "":
            parts.append("")
        parts.append(block_text)
        parts.append("")
        return parts

    def _consume_fence(self, lines: List[str], index: int) -> tuple[BlockNode, int]:
        fence_lines = [lines[index]]
        index += 1
        while index < len(lines):
            fence_lines.append(lines[index])
            if re.match(r"^```", lines[index].strip()):
                index += 1
                break
            index += 1
        return BlockNode(kind="fence", lines=fence_lines), index

    def _consume_div(self, lines: List[str], index: int) -> tuple[BlockNode, int]:
        opening = lines[index].strip()
        div_type = opening.replace(":::", "", 1).strip().strip("{}").strip().lower()
        if div_type.startswith("."):
            div_type = div_type[1:]
        if " " in div_type:
            div_type = div_type.split()[0]

        body: List[str] = []
        index += 1
        while index < len(lines):
            if re.match(r"^:::\s*$", lines[index].strip()):
                index += 1
                break
            body.append(lines[index])
            index += 1
        return BlockNode(kind="div", lines=body, meta={"div_type": div_type}), index

    def _consume_list(self, lines: List[str], index: int) -> tuple[BlockNode, int]:
        items: List[str] = []
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if stripped == "":
                break
            if not self._is_list_item(stripped) and not re.match(r"^\s{2,}\S", line):
                break
            items.append(line)
            index += 1
        return BlockNode(kind="list", lines=items), index

    def _consume_paragraph(self, lines: List[str], index: int) -> tuple[BlockNode, int]:
        paragraph_lines: List[str] = []
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if stripped == "":
                break
            if re.match(r"^```", stripped) or re.match(r"^:::\s*", stripped):
                break
            if re.match(r"^#{1,6}\s*", stripped) or self._is_list_item(stripped):
                break
            paragraph_lines.append(line)
            index += 1
        return BlockNode(kind="paragraph", lines=paragraph_lines), index

    def _is_list_item(self, stripped: str) -> bool:
        return bool(re.match(r"^([-*+]|\d+\.)\s+", stripped))
