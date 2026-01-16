#!/usr/bin/env python3
"""
智能 Markdown 格式化工具
将 Pandoc EPUB 转换的残留标记转换为标准 Markdown 格式
保留有用信息,删除冗余标记
"""
import re
import sys
from pathlib import Path
from typing import List, Dict


class SmartMarkdownFormatter:
    """智能 Markdown 格式化器"""

    def __init__(self):
        self.stats = {
            'headers_normalized': 0,
            'quotes_converted': 0,
            'emphasis_converted': 0,
            'anchors_removed': 0,
            'html_cleaned': 0,
            'toc_preserved': 0,
            'images_fixed': 0,
            'code_blocks_preserved': 0,
            'book_formatting_enhanced': 0,
        }
        self.in_toc = False  # 是否在目录区域

    def format(self, text: str) -> str:
        """执行所有格式化步骤"""
        # 步骤 1: 保护代码块 (先提取出来,最后再插入回去)
        text, code_blocks = self.extract_code_blocks(text)

        # 步骤 2: 格式化处理
        text = self.preserve_and_clean_toc(text)
        text = self.normalize_headers(text)
        text = self.convert_quotes(text)
        text = self.convert_emphasis(text)
        text = self.clean_images(text)
        text = self.remove_html_comments(text)
        text = self.remove_anchors(text)
        text = self.remove_calibre_classes(text)
        text = self.remove_pandoc_divs(text)
        text = self.clean_links(text)
        text = self.enhance_book_formatting(text)
        text = self.normalize_whitespace(text)
        text = self.fix_list_formatting(text)

        # 步骤 3: 恢复代码块
        text = self.restore_code_blocks(text, code_blocks)

        return text.strip() + '\n'

    def extract_code_blocks(self, text: str) -> tuple:
        """
        提取并保护代码块,避免被格式化破坏

        注意: 只保护真正的代码块,不保护 Pandoc 残留的 HTML 注释

        Returns:
            (处理后的文本, 代码块列表)
        """
        code_blocks = []
        placeholder_pattern = "___CODE_BLOCK_{}___"

        def replace_code_block(match):
            content = match.group(0)

            # 排除 Pandoc HTML 注释: `<!--...-->`{=html}
            if re.match(r'`<!--.*?-->`(\{=html\})?', content):
                return content  # 不保护,让后续步骤删除

            block_index = len(code_blocks)
            code_blocks.append(content)
            self.stats['code_blocks_preserved'] += 1
            return placeholder_pattern.format(block_index)

        # 匹配代码块 (``` ... ```)
        text = re.sub(
            r'```[\s\S]*?```',
            replace_code_block,
            text
        )

        # 匹配行内代码 (`code`)
        # 但排除 Pandoc 注释
        text = re.sub(
            r'`[^`\n]+`(\{[^}]+\})?',
            replace_code_block,
            text
        )

        return text, code_blocks

    def restore_code_blocks(self, text: str, code_blocks: List[str]) -> str:
        """
        恢复代码块

        Args:
            text: 处理后的文本
            code_blocks: 代码块列表

        Returns:
            恢复代码块后的文本
        """
        for i, block in enumerate(code_blocks):
            placeholder = f"___CODE_BLOCK_{i}___"
            text = text.replace(placeholder, block)

        return text

    def enhance_book_formatting(self, text: str) -> str:
        """
        增强书籍排版美观性

        - 在章节标题前后添加合适的空行
        - 优化段落间距
        - 美化列表格式
        - 优化引用块格式
        """
        lines = []
        prev_line_type = None

        for i, line in enumerate(text.split('\n')):
            stripped = line.strip()

            # 检测当前行类型
            if re.match(r'^#{1,6}\s+', stripped):
                current_type = 'header'
            elif re.match(r'^>\s+', stripped):
                current_type = 'quote'
            elif re.match(r'^[-*+]\s+', stripped):
                current_type = 'list'
            elif re.match(r'^\d+\.\s+', stripped):
                current_type = 'ordered_list'
            elif not stripped:
                current_type = 'empty'
            else:
                current_type = 'paragraph'

            # 根据类型转换添加适当空行
            if current_type == 'header' and prev_line_type not in [None, 'empty', 'header']:
                # 章节标题前添加空行
                if lines and lines[-1].strip():
                    lines.append('')

            if prev_line_type == 'header' and current_type not in ['empty', 'header']:
                # 章节标题后添加空行
                if lines and lines[-1].strip():
                    lines.append('')

            lines.append(line)

            if current_type != 'empty':
                prev_line_type = current_type

        self.stats['book_formatting_enhanced'] = 1
        return '\n'.join(lines)

    def preserve_and_clean_toc(self, text: str) -> str:
        """保留并清理目录"""
        lines = []
        in_toc = False
        toc_lines = []

        for line in text.split('\n'):
            # 检测目录开始
            if re.match(r'##\s+(目录|Table of Contents|Contents|Topology of Contents)', line, re.IGNORECASE):
                in_toc = True
                lines.append('\n## 目录\n')
                self.stats['toc_preserved'] += 1
                continue

            # 检测目录结束 (遇到下一个章节标题)
            if in_toc and re.match(r'^##\s+(?!目录)', line):
                in_toc = False
                # 处理收集到的目录行
                cleaned_toc = self._clean_toc_lines(toc_lines)
                lines.extend(cleaned_toc)
                lines.append('')  # 目录后加空行
                toc_lines = []

            if in_toc:
                toc_lines.append(line)
            else:
                lines.append(line)

        # 处理末尾的目录
        if toc_lines:
            cleaned_toc = self._clean_toc_lines(toc_lines)
            lines.extend(cleaned_toc)

        return '\n'.join(lines)

    def _clean_toc_lines(self, lines: List[str]) -> List[str]:
        """清理目录行"""
        cleaned = []
        for line in lines:
            # 跳过 ::: 块标记
            if line.strip() in [':::', '::: tableofcontents']:
                continue

            # 移除 Pandoc 链接的类属性但保留链接本身
            # [ [text](#link){.class}]{.class} → - [text](#link)

            # 处理列表项
            if re.search(r'\[.*?\]\(#.*?\)', line):
                # 提取链接文本和目标
                match = re.search(r'\[\s*\[([^\]]+)\]\((#[^)]+)\)[^]]*\]', line)
                if match:
                    text = match.group(1)
                    link = match.group(2)
                    # 判断缩进级别
                    if line.strip().startswith('['):
                        cleaned.append(f'- [{text}]({link})')
                    else:
                        cleaned.append(f'  - [{text}]({link})')
                    continue

            # 处理部分标题 (Part I, Part II)
            if re.search(r'^[IVX]+\s+\[', line):
                match = re.search(r'([IVX]+)\s+\[([^\]]+)\]', line)
                if match:
                    part_num = match.group(1)
                    part_title = match.group(2)
                    cleaned.append(f'\n**第 {part_num} 部分: {part_title}**\n')
                    continue

            # 移除反斜杠换行
            line = line.replace('\\\n', '').replace('\\', '')

            if line.strip():
                cleaned.append(line)

        return cleaned

    def normalize_headers(self, text: str) -> str:
        """标准化标题格式"""
        lines = []

        for line in text.split('\n'):
            # 匹配带有类属性的标题
            # ## []{#id .class}Title {.class}
            header_match = re.match(r'^(#{1,6})\s*', line)

            if header_match:
                level = header_match.group(1)
                rest = line[len(header_match.group(0)):]

                # 移除所有锚点和类
                rest = re.sub(r'\[\]\{[^}]+\}', '', rest)
                rest = re.sub(r'\[([^\]]+)\]\{[^}]+\}', r'\1', rest)
                rest = re.sub(r'\{[^}]+\}', '', rest)

                # 重建标题
                clean_title = rest.strip()
                if clean_title:
                    lines.append(f'{level} {clean_title}')
                    self.stats['headers_normalized'] += 1
                continue

            lines.append(line)

        return '\n'.join(lines)

    def convert_quotes(self, text: str) -> str:
        """转换引用块"""
        # ::: quote ... ::: → > ...
        in_quote = False
        lines = []

        for line in text.split('\n'):
            if re.match(r'^:::\s*(quote|center|block)?', line):
                if not in_quote:
                    in_quote = True
                else:
                    in_quote = False
                self.stats['quotes_converted'] += 1
                continue

            if in_quote and line.strip():
                lines.append(f'> {line}')
            else:
                lines.append(line)

        return '\n'.join(lines)

    def convert_emphasis(self, text: str) -> str:
        """转换强调格式"""
        # [text]{.emphasis} → **text**
        # [text]{.italic} → *text*

        # 强调 (加粗)
        text = re.sub(
            r'\[([^\]]+)\]\{\.emphasis\}',
            r'**\1**',
            text
        )

        # 斜体
        text = re.sub(
            r'\[([^\]]+)\]\{\.italic\}',
            r'*\1*',
            text
        )

        self.stats['emphasis_converted'] += text.count('**') + text.count('*')
        return text

    def clean_images(self, text: str) -> str:
        """清理图片语法"""
        def fix_image(match):
            alt = match.group(1) or ''
            path = match.group(2)

            # 提取文件名
            filename = Path(path).name

            # 修复路径
            if 'images/' in path:
                relative_path = 'images/' + filename
            else:
                relative_path = filename

            # 清理 alt 文本
            if alt.upper() == 'PIC' or not alt:
                alt = filename.split('.')[0]  # 使用文件名作为 alt

            self.stats['images_fixed'] += 1
            return f'![{alt}]({relative_path})'

        # 匹配 ![alt](path){.class}
        text = re.sub(
            r'!\[([^\]]*)\]\(([^)]+)\)\{[^}]*\}',
            fix_image,
            text
        )

        # 简化 ![PIC](path)
        text = re.sub(
            r'!\[PIC\]\(([^)]+)\)',
            lambda m: f'![{Path(m.group(1)).stem}]({m.group(1)})',
            text
        )

        return text

    def remove_html_comments(self, text: str) -> str:
        """移除 HTML 注释"""
        count_before = len(text)
        text = re.sub(r'`<!--.*?-->`\{=html\}', '', text)
        text = re.sub(r'<!--.*?-->', '', text)
        count_after = len(text)
        if count_before != count_after:
            self.stats['html_cleaned'] += 1
        return text

    def remove_anchors(self, text: str) -> str:
        """移除锚点"""
        patterns = [
            r'\[\]\{#[^}]+\}',
            r'\{#[A-Za-z0-9_\-\.]+\}',
            r'\[\]\{\.image[^}]*\}',
        ]

        for pattern in patterns:
            count = len(re.findall(pattern, text))
            self.stats['anchors_removed'] += count
            text = re.sub(pattern, '', text)

        return text

    def remove_calibre_classes(self, text: str) -> str:
        """移除 Calibre 和 Pandoc 类名"""
        # 移除内联的类属性
        patterns = [
            r'\{\.calibre\d+\}',
            r'\{\.ecrm\}',
            r'\{\.ecti\}',
            r'\{\.ecss\}',
            r'\{\.likechapterhead\}',
            r'\{\.parthead\}',
            r'\{\.chaptertoc\}',
            r'\{\.parttoc\}',
        ]

        for pattern in patterns:
            text = re.sub(pattern, '', text)

        # 移除 span 标签: [text]{.class} → text
        text = re.sub(r'\[([^\]]+)\]\{[^}]+\}', r'\1', text)

        return text

    def remove_pandoc_divs(self, text: str) -> str:
        """移除 Pandoc div 块 (已在 convert_quotes 中处理大部分)"""
        # 移除空的 ::: 行
        text = re.sub(r'^:::\s*$', '', text, flags=re.MULTILINE)
        return text

    def clean_links(self, text: str) -> str:
        """清理链接"""
        # 移除链接的类属性: [text](#link){.class} → [text](#link)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)\{[^}]+\}', r'[\1](\2)', text)

        # 移除外层括号: [ [text](#link) ]{.class} → [text](#link)
        text = re.sub(r'\[\s*\[([^\]]+)\]\(([^)]+)\)\s*\]\{[^}]+\}', r'[\1](\2)', text)

        return text

    def normalize_whitespace(self, text: str) -> str:
        """标准化空白"""
        # 最多2个连续空行
        text = re.sub(r'\n\n\n+', '\n\n', text)

        # 移除行尾空格
        text = re.sub(r' +$', '', text, flags=re.MULTILINE)

        return text

    def fix_list_formatting(self, text: str) -> str:
        """修复列表格式"""
        # 移除反斜杠换行
        text = re.sub(r'\\\s*\n', '\n', text)
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


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python smart_markdown_formatter.py <input_file> [output_file]")
        print("\n这个工具会:")
        print("  ✅ 保留并清理目录")
        print("  ✅ 保护代码块格式")
        print("  ✅ 标准化标题格式")
        print("  ✅ 转换引用块和强调格式")
        print("  ✅ 修复图片路径")
        print("  ✅ 优化书籍排版")
        print("  ✅ 移除冗余标记")
        print("\n示例:")
        print("  python smart_markdown_formatter.py input.md")
        print("  python smart_markdown_formatter.py input.md output_formatted.md")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"❌ 错误: 文件不存在: {input_file}")
        sys.exit(1)

    # 确定输出文件
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        output_file = input_file.parent / f"{input_file.stem}_formatted{input_file.suffix}"

    print(f"📖 读取文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        sys.exit(1)

    print(f"✨ 格式化中...")
    formatter = SmartMarkdownFormatter()
    formatted_content = formatter.format(content)

    print(f"💾 保存到: {output_file}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        sys.exit(1)

    formatter.print_stats()

    # 显示文件大小对比
    original_size = input_file.stat().st_size
    formatted_size = output_file.stat().st_size
    reduction = (1 - formatted_size / original_size) * 100

    print(f"\n📏 文件大小:")
    print(f"  - 原始: {original_size:,} 字节")
    print(f"  - 格式化后: {formatted_size:,} 字节")
    if reduction > 0:
        print(f"  - 减少: {reduction:.1f}%")
    else:
        print(f"  - 增加: {abs(reduction):.1f}%")

    print(f"\n✅ 完成! 输出文件: {output_file}")


if __name__ == '__main__':
    main()
