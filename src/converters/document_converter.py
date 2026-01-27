"""
文档转换器
支持 PDF 和 EPUB 转 Markdown
"""
import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DocumentConverter:
    """文档转换器"""

    def __init__(self):
        self._check_dependencies()

    def _check_dependencies(self):
        """检查依赖工具是否安装"""
        try:
            subprocess.run(['marker_single', '--version'],
                         capture_output=True, check=False)
            self.has_marker = True
        except FileNotFoundError:
            logger.warning("marker_single 未安装,PDF 转换将不可用")
            self.has_marker = False

        try:
            subprocess.run(['pandoc', '--version'],
                         capture_output=True, check=False)
            self.has_pandoc = True
        except FileNotFoundError:
            logger.warning("pandoc 未安装,EPUB 转换将不可用")
            self.has_pandoc = False

    def pdf_to_markdown(
        self,
        pdf_path: Path,
        output_dir: Path
    ) -> Optional[Path]:
        """
        PDF 转 Markdown (使用 marker)

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录

        Returns:
            生成的 Markdown 文件路径
        """
        if not self.has_marker:
            raise RuntimeError(
                "marker_single 未安装。请安装: pip install marker-pdf"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        # 运行 marker (新版本命令格式)
        cmd = [
            'marker_single',
            str(pdf_path),
            '--output_dir', str(output_dir),
            '--output_format', 'markdown'
        ]

        logger.info(f"正在转换 PDF: {pdf_path.name}")
        logger.info(f"命令: {' '.join(cmd)}")
        
        # 修改: 不捕获输出，直接显示在终端，以便用户看到 marker 的进度条
        # result = subprocess.run(cmd, capture_output=True, text=True)
        result = subprocess.run(cmd, check=False)

        if result.returncode != 0:
            logger.error(f"PDF 转换失败 (退出码: {result.returncode})")
            raise RuntimeError(f"PDF 转换失败")

        # 查找生成的 Markdown 文件 (marker 可能会在子目录中生成)
        # 1. 直接在 output_dir 中查找
        md_file = output_dir / f"{pdf_path.stem}.md"
        if md_file.exists():
            logger.info(f"PDF 转换成功: {md_file}")
            return md_file

        # 2. 在以文件名命名的子目录中查找
        subdir = output_dir / pdf_path.stem
        if subdir.exists():
            md_file = subdir / f"{pdf_path.stem}.md"
            if md_file.exists():
                logger.info(f"PDF 转换成功: {md_file}")
                return md_file

        # 3. 递归查找所有 .md 文件
        md_files = list(output_dir.rglob("*.md"))
        if md_files:
            # 返回第一个找到的 md 文件
            md_file = md_files[0]
            logger.info(f"PDF 转换成功 (搜索到): {md_file}")
            return md_file

        raise RuntimeError(f"PDF 转换完成但未找到 Markdown 文件，请检查输出目录: {output_dir}")

    def epub_to_markdown(
        self,
        epub_path: Path,
        output_dir: Path
    ) -> Optional[Path]:
        """
        EPUB 转 Markdown (使用 pandoc)

        Args:
            epub_path: EPUB 文件路径
            output_dir: 输出目录

        Returns:
            生成的 Markdown 文件路径
        """
        if not self.has_pandoc:
            raise RuntimeError(
                "pandoc 未安装。请安装: brew install pandoc (macOS) 或 apt install pandoc (Linux)"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        md_file = output_dir / f"{epub_path.stem}.md"

        # 运行 pandoc
        cmd = [
            'pandoc',
            str(epub_path),
            '-o', str(md_file),
            '--extract-media', str(output_dir / 'images'),
            '--wrap=none'
        ]

        logger.info(f"正在转换 EPUB: {epub_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"EPUB 转换失败: {result.stderr}")
            return None

        if md_file.exists():
            logger.info(f"EPUB 转换成功: {md_file}")
            return md_file

        return None

    def convert(
        self,
        input_path: Path,
        output_dir: Path
    ) -> Optional[Path]:
        """
        智能转换(自动识别文件类型)

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录

        Returns:
            生成的 Markdown 文件路径
        """
        suffix = input_path.suffix.lower()

        if suffix == '.pdf':
            return self.pdf_to_markdown(input_path, output_dir)
        elif suffix in ['.epub', '.mobi']:
            return self.epub_to_markdown(input_path, output_dir)
        elif suffix in ['.md', '.markdown']:
            logger.info(f"文件已经是 Markdown 格式: {input_path}")
            return input_path
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")
