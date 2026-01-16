#!/usr/bin/env python3
"""
高级 Markdown 格式清理工具
专门处理 EPUB → Markdown 转换后的残留标记和格式问题
"""
import re
import sys
from pathlib import Path


class AdvancedMarkdownCleaner:
    """增强版 Markdown 清理器"""

    def __init__(self):
        self.stats = {
            'html_comments': 0,
            'empty_anchors': 0,
            'calibre_classes': 0,
            'pandoc_directives': 0,
            'excessive_newlines': 0,
            'image_paths_fixed': 0,
            'span_tags': 0,
            'div_blocks': 0,
            'inline_styles': 0,
        }

    def clean(self, text: str) -> str:
        """执行所有清理步骤"""
        text = self.remove_html_comments(text)
        text = self.remove_empty_anchors(text)
        text = self.remove_calibre_classes(text)
        text = self.remove_pandoc_directives(text)
        text = self.clean_image_syntax(text)
        text = self.remove_span_tags(text)
        text = self.remove_div_blocks(text)
        text = self.clean_link_syntax(text)
        text = self.remove_inline_styles(text)
        text = self.fix_header_syntax(text)
        text = self.clean_excessive_newlines(text)
        text = self.fix_list_formatting(text)
        text = self.remove_empty_lines_in_headers(text)
        return text.strip() + '\n'

    def remove_html_comments(self, text: str) -> str:
        """移除 HTML 注释"""
        # <!--l. 59-->
        pattern = r'`<!--.*?-->`\{=html\}'
        count = len(re.findall(pattern, text))
        self.stats['html_comments'] += count
        text = re.sub(pattern, '', text)

        # 普通 HTML 注释
        text = re.sub(r'<!--.*?-->', '', text)
        return text

    def remove_empty_anchors(self, text: str) -> str:
        """移除空锚点标记"""
        # []{#ANickLandReader_split_000.html}
        # []{#ANickLandReader_split_000.html_x1-1000}
        patterns = [
            r'\[\]\{#[^}]+\}',
            r'\[\]\{\.image[^}]*\}',
            r'\[PIC\]\([^)]+\)\{[^}]*\}',
        ]
        for pattern in patterns:
            count = len(re.findall(pattern, text))
            self.stats['empty_anchors'] += count
            text = re.sub(pattern, '', text)
        return text

    def remove_calibre_classes(self, text: str) -> str:
        """移除 Calibre 类名和属性"""
        # {.calibre1}, {.calibre2}, {#id .class}
        patterns = [
            r'\{\.calibre\d+\}',
            r'\{#[^}]+\s+\.calibre\d+\}',
            r'\{#[^}]+\s+\.[a-z]+\}',
            r'\{\.ecrm\}',
            r'\{\.ecti\}',
            r'\{\.ecss\}',
            r'\{\.chaptertoc\}',
            r'\{\.parttoc\}',
            r'\{\.likechapterhead\}',
            r'\{\.parthead\}',
            r'\{\.center\}',
            r'\{\.quote\}',
        ]
        for pattern in patterns:
            count = len(re.findall(pattern, text))
            self.stats['calibre_classes'] += count
            text = re.sub(pattern, '', text)
        return text

    def remove_pandoc_directives(self, text: str) -> str:
        """移除 Pandoc 特殊指令"""
        # ::: tableofcontents ... :::
        # ::: {#id .class} ... :::
        self.stats['pandoc_directives'] += len(re.findall(r':::', text))
        text = re.sub(r'^:::\s+\{?[^}]*\}?\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^:::\s*$', '', text, flags=re.MULTILINE)
        return text

    def clean_image_syntax(self, text: str) -> str:
        """清理图片语法"""
        # ![PIC](/absolute/path/image.jpg){.calibre1}
        # → ![](images/image.jpg)

        def fix_image_path(match):
            alt = match.group(1) or ''
            path = match.group(2)

            # 提取文件名
            filename = Path(path).name

            # 如果有 images/ 路径,保留相对路径
            if 'images/' in path:
                relative_path = 'images/' + filename
            else:
                relative_path = filename

            self.stats['image_paths_fixed'] += 1

            # 清理 alt 文本
            if alt.upper() == 'PIC' or not alt:
                return f'![{filename}]({relative_path})'
            return f'![{alt}]({relative_path})'

        # 匹配图片语法
        text = re.sub(
            r'!\[([^\]]*)\]\(([^)]+)\)\{[^}]*\}',
            fix_image_path,
            text
        )

        # 简化没有属性的图片
        text = re.sub(
            r'!\[PIC\]\(([^)]+)\)',
            lambda m: f'![{Path(m.group(1)).name}]({m.group(1)})',
            text
        )

        return text

    def remove_span_tags(self, text: str) -> str:
        """移除 span 标签及其内容分割"""
        # [text1]{.class} [text2]{.class} → text1 text2

        # 先移除带类的 span
        def merge_spans(match):
            self.stats['span_tags'] += 1
            return match.group(1)

        # 匹配 [content]{.class}
        text = re.sub(r'\[([^\]]+)\]\{[^}]+\}', merge_spans, text)

        # 合并被错误分割的句子
        text = re.sub(r'\]\{[^}]+\}\s+\[', '', text)

        return text

    def remove_div_blocks(self, text: str) -> str:
        """移除 div 块"""
        # ::: center ... :::
        # ::: quote ... :::

        in_block = False
        block_content = []
        result = []

        for line in text.split('\n'):
            if line.strip().startswith(':::'):
                if not in_block:
                    in_block = True
                    block_content = []
                else:
                    # 结束块,输出内容
                    if block_content:
                        result.extend(block_content)
                    in_block = False
                    self.stats['div_blocks'] += 1
            elif in_block:
                block_content.append(line)
            else:
                result.append(line)

        return '\n'.join(result)

    def clean_link_syntax(self, text: str) -> str:
        """清理链接语法"""
        # [ [text](#link){.class}]{.class} → [text](#link)

        # 移除链接的类属性
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)\{[^}]+\}', r'[\1](\2)', text)

        # 移除外层的括号和类
        text = re.sub(r'\[\s*\[([^\]]+)\]\(([^)]+)\)\s*\]\{[^}]+\}', r'[\1](\2)', text)

        # 移除内部链接的锚点(对翻译后的文档无用)
        text = re.sub(r'\[([^\]]+)\]\(#[^)]+\)', r'\1', text)

        return text

    def remove_inline_styles(self, text: str) -> str:
        """移除内联样式"""
        # {style="..."}
        count = len(re.findall(r'\{style="[^"]*"\}', text))
        self.stats['inline_styles'] += count
        text = re.sub(r'\{style="[^"]*"\}', '', text)
        return text

    def fix_header_syntax(self, text: str) -> str:
        """修复标题语法"""
        # ## []{.class}text {.class} → ## text

        lines = []
        for line in text.split('\n'):
            # 移除标题中的空锚点
            line = re.sub(r'^(#+)\s+\[\]\{[^}]+\}', r'\1', line)

            # 移除标题中的类属性
            line = re.sub(r'^(#+\s+.+?)\s+\{[^}]+\}', r'\1', line)

            # 移除标题中的内联span
            line = re.sub(r'^(#+)\s+\[([^\]]+)\]\{[^}]+\}', r'\1 \2', line)

            lines.append(line)

        return '\n'.join(lines)

    def clean_excessive_newlines(self, text: str) -> str:
        """清理过多的空行"""
        # 最多保留2个连续空行
        original_count = len(re.findall(r'\n\n\n+', text))
        text = re.sub(r'\n\n\n+', '\n\n', text)
        self.stats['excessive_newlines'] += original_count
        return text

    def fix_list_formatting(self, text: str) -> str:
        """修复列表格式"""
        # 移除列表中的反斜杠换行符
        text = re.sub(r'\\\s*\n', '\n', text)
        return text

    def remove_empty_lines_in_headers(self, text: str) -> str:
        """移除标题前后多余的空行"""
        lines = []
        prev_empty = False

        for line in text.split('\n'):
            is_empty = not line.strip()
            is_header = line.strip().startswith('#')

            if is_empty:
                if not prev_empty:
                    lines.append(line)
                prev_empty = True
            else:
                if is_header and lines and lines[-1].strip():
                    lines.append('')  # 标题前加一个空行
                lines.append(line)
                prev_empty = False

        return '\n'.join(lines)

    def print_stats(self):
        """打印清理统计"""
        print("\n📊 清理统计:")
        print(f"  - HTML 注释: {self.stats['html_comments']}")
        print(f"  - 空锚点: {self.stats['empty_anchors']}")
        print(f"  - Calibre 类: {self.stats['calibre_classes']}")
        print(f"  - Pandoc 指令: {self.stats['pandoc_directives']}")
        print(f"  - 图片路径修复: {self.stats['image_paths_fixed']}")
        print(f"  - Span 标签: {self.stats['span_tags']}")
        print(f"  - Div 块: {self.stats['div_blocks']}")
        print(f"  - 内联样式: {self.stats['inline_styles']}")
        print(f"  - 过多空行: {self.stats['excessive_newlines']}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python advanced_markdown_cleaner.py <input_file> [output_file]")
        print("\n示例:")
        print("  python advanced_markdown_cleaner.py input.md")
        print("  python advanced_markdown_cleaner.py input.md output.md")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"❌ 错误: 文件不存在: {input_file}")
        sys.exit(1)

    # 确定输出文件
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        # 默认输出到 xxx_cleaned.md
        output_file = input_file.parent / f"{input_file.stem}_cleaned{input_file.suffix}"

    print(f"📖 读取文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        sys.exit(1)

    print(f"🧹 清理中...")
    cleaner = AdvancedMarkdownCleaner()
    cleaned_content = cleaner.clean(content)

    print(f"💾 保存到: {output_file}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        sys.exit(1)

    cleaner.print_stats()

    # 显示文件大小对比
    original_size = input_file.stat().st_size
    cleaned_size = output_file.stat().st_size
    reduction = (1 - cleaned_size / original_size) * 100

    print(f"\n📏 文件大小:")
    print(f"  - 原始: {original_size:,} 字节")
    print(f"  - 清理后: {cleaned_size:,} 字节")
    print(f"  - 减少: {reduction:.1f}%")

    print(f"\n✅ 完成!")


if __name__ == '__main__':
    main()
