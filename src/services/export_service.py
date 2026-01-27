"""
导出服务
支持多种格式导出翻译结果
"""
import re
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class BilingualParagraph:
    """双语段落"""
    source: str
    translation: str


class ExportService:
    """导出服务"""

    # HTML 模板 - 双栏布局
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 双语对照</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                         'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            line-height: 1.8;
            color: #333;
            background: #f5f5f5;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 12px;
        }}

        header h1 {{
            font-size: 2rem;
            margin-bottom: 10px;
        }}

        header p {{
            opacity: 0.9;
            font-size: 1rem;
        }}

        .bilingual-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .source-col, .translation-col {{
            flex: 1;
            padding: 20px;
        }}

        .source-col {{
            background: #fafafa;
            border-right: 1px solid #eee;
            color: #666;
        }}

        .translation-col {{
            background: white;
        }}

        .source-col p, .translation-col p {{
            margin-bottom: 1em;
        }}

        .source-col p:last-child, .translation-col p:last-child {{
            margin-bottom: 0;
        }}

        .paragraph-number {{
            display: inline-block;
            background: #667eea;
            color: white;
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 4px;
            margin-bottom: 10px;
        }}

        .source-col .paragraph-number {{
            background: #999;
        }}

        /* 响应式布局 */
        @media (max-width: 768px) {{
            .bilingual-row {{
                flex-direction: column;
            }}

            .source-col {{
                border-right: none;
                border-bottom: 1px solid #eee;
            }}
        }}

        /* 打印样式 */
        @media print {{
            body {{
                background: white;
            }}

            header {{
                background: #333;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}

            .bilingual-row {{
                break-inside: avoid;
                box-shadow: none;
                border: 1px solid #ddd;
            }}
        }}

        /* Markdown 样式 */
        h1, h2, h3, h4, h5, h6 {{
            margin: 0.5em 0;
            font-weight: 600;
        }}

        h1 {{ font-size: 1.5em; }}
        h2 {{ font-size: 1.3em; }}
        h3 {{ font-size: 1.1em; }}

        strong {{ font-weight: 600; }}
        em {{ font-style: italic; }}

        a {{
            color: #667eea;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 0.9em;
        }}

        blockquote {{
            border-left: 3px solid #667eea;
            padding-left: 15px;
            margin: 1em 0;
            color: #666;
        }}

        img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <p>双语对照阅读 | Bilingual Reading</p>
        </header>

        <main>
{content}
        </main>
    </div>
</body>
</html>
"""

    BILINGUAL_ROW_TEMPLATE = """            <div class="bilingual-row">
                <div class="source-col">
                    <span class="paragraph-number">原文 #{index}</span>
                    {source}
                </div>
                <div class="translation-col">
                    <span class="paragraph-number">译文 #{index}</span>
                    {translation}
                </div>
            </div>
"""

    @classmethod
    def parse_bilingual_markdown(cls, content: str) -> List[BilingualParagraph]:
        """
        解析双语对照 Markdown 文件

        格式:
        > 原文段落 (英文)...

        译文段落 (中文)...

        ---

        Args:
            content: Markdown 文件内容

        Returns:
            双语段落列表
        """
        paragraphs = []

        # 按分隔线分割
        sections = re.split(r'\n---+\n', content)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 查找引用块 (原文) 和普通文本 (译文)
            # 引用块格式: > 开头的行
            lines = section.split('\n')

            source_lines = []
            translation_lines = []
            in_quote = False
            quote_ended = False

            for line in lines:
                # 检查是否是引用行
                if line.startswith('>'):
                    # 如果已经结束引用区域，这行属于译文中的引用
                    if quote_ended:
                        translation_lines.append(line)
                    else:
                        in_quote = True
                        # 移除 > 前缀
                        cleaned = line[1:].lstrip() if len(line) > 1 else ''
                        source_lines.append(cleaned)
                else:
                    # 非引用行
                    if in_quote and line.strip():
                        # 第一个非空非引用行，标记引用结束
                        quote_ended = True
                        in_quote = False
                    if quote_ended or (not in_quote and not source_lines):
                        # 已经进入译文区域，或者还没开始引用
                        if quote_ended:
                            translation_lines.append(line)

            source = '\n'.join(source_lines).strip()
            translation = '\n'.join(translation_lines).strip()

            # 过滤条件：
            # 1. 原文应该主要是英文（包含连续英文单词）
            # 2. 译文应该主要是中文
            # 3. 跳过纯图片/元数据段落
            has_english_source = bool(re.search(r'[a-zA-Z]{4,}', source))
            has_chinese_translation = bool(re.search(r'[\u4e00-\u9fff]{2,}', translation))

            # 跳过元数据和图片段落
            is_metadata = '由 AI 自动翻译' in source or '源文件:' in source
            is_image_only = source.startswith('![') or source.startswith('<svg')

            if (source and translation and
                has_english_source and has_chinese_translation and
                not is_metadata and not is_image_only):
                paragraphs.append(BilingualParagraph(source=source, translation=translation))

        return paragraphs

    @classmethod
    def markdown_to_html(cls, text: str) -> str:
        """
        简单的 Markdown 转 HTML

        Args:
            text: Markdown 文本

        Returns:
            HTML 文本
        """
        # 转义 HTML 特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')

        # 标题
        text = re.sub(r'^###### (.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
        text = re.sub(r'^##### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # 粗体和斜体
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

        # 链接
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        # 段落
        paragraphs = text.split('\n\n')
        html_paragraphs = []
        for p in paragraphs:
            p = p.strip()
            if p:
                # 如果已经是 HTML 标签开头,不包装
                if p.startswith('<h') or p.startswith('<blockquote'):
                    html_paragraphs.append(p)
                else:
                    # 将单个换行转为 <br>
                    p = p.replace('\n', '<br>\n')
                    html_paragraphs.append(f'<p>{p}</p>')

        return '\n'.join(html_paragraphs)

    @classmethod
    def export_bilingual_html(
        cls,
        markdown_path: str,
        output_path: str = None,
        title: str = None
    ) -> str:
        """
        将双语对照 Markdown 导出为 HTML

        Args:
            markdown_path: Markdown 文件路径
            output_path: 输出 HTML 路径 (默认与 Markdown 同目录)
            title: 文档标题

        Returns:
            输出文件路径
        """
        markdown_path = Path(markdown_path)

        if output_path is None:
            output_path = markdown_path.with_suffix('.html')
        else:
            output_path = Path(output_path)

        if title is None:
            title = markdown_path.stem

        # 读取 Markdown
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析双语段落
        paragraphs = cls.parse_bilingual_markdown(content)

        # 生成 HTML 内容
        html_content = []
        for i, para in enumerate(paragraphs, 1):
            source_html = cls.markdown_to_html(para.source)
            translation_html = cls.markdown_to_html(para.translation)

            row = cls.BILINGUAL_ROW_TEMPLATE.format(
                index=i,
                source=source_html,
                translation=translation_html
            )
            html_content.append(row)

        # 生成完整 HTML
        html = cls.HTML_TEMPLATE.format(
            title=title,
            content='\n'.join(html_content)
        )

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return str(output_path)

    @classmethod
    def export_from_pairs(
        cls,
        pairs: List[Tuple[str, str]],
        output_path: str,
        title: str = "翻译结果"
    ) -> str:
        """
        从原文-译文对列表导出 HTML

        Args:
            pairs: [(原文, 译文), ...] 列表
            output_path: 输出路径
            title: 文档标题

        Returns:
            输出文件路径
        """
        html_content = []
        for i, (source, translation) in enumerate(pairs, 1):
            source_html = cls.markdown_to_html(source)
            translation_html = cls.markdown_to_html(translation)

            row = cls.BILINGUAL_ROW_TEMPLATE.format(
                index=i,
                source=source_html,
                translation=translation_html
            )
            html_content.append(row)

        html = cls.HTML_TEMPLATE.format(
            title=title,
            content='\n'.join(html_content)
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path


# CLI 入口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python export_service.py <markdown_file> [output_html]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    result = ExportService.export_bilingual_html(input_file, output_file)
    print(f"导出成功: {result}")
