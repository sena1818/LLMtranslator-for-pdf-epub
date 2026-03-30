#!/usr/bin/env python3
"""
智能 Markdown 格式化工具
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.markdown_formatter import SmartMarkdownFormatter


def main():
    """主函数"""
    args = sys.argv[1:]
    source_type = "epub"
    positional_args = []

    for arg in args:
        if arg.startswith("--source-type="):
            source_type = arg.split("=", 1)[1].strip() or "epub"
            continue
        positional_args.append(arg)

    if len(positional_args) < 1:
        print(
            "用法: python smart_markdown_formatter.py <input_file> [output_file] [--source-type=epub]"
        )
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
        print("  python smart_markdown_formatter.py input.md --source-type=kindle")
        sys.exit(1)

    input_file = Path(positional_args[0])
    if not input_file.exists():
        print(f"❌ 错误: 文件不存在: {input_file}")
        sys.exit(1)

    if len(positional_args) >= 2:
        output_file = Path(positional_args[1])
    else:
        output_file = input_file.parent / f"{input_file.stem}_formatted{input_file.suffix}"

    if output_file.resolve() == input_file.resolve():
        print("❌ 错误: 输入文件和输出文件不能是同一个路径")
        print("💡 请输出到一个新文件，确认无误后再替换原文件")
        sys.exit(1)

    print(f"📖 读取文件: {input_file}")
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            content = file.read()
    except Exception as exc:
        print(f"❌ 读取失败: {exc}")
        sys.exit(1)

    print(f"✨ 格式化中... (source_type={source_type})")
    formatter = SmartMarkdownFormatter()
    formatted_content = formatter.format(content, source_type=source_type)

    print(f"💾 保存到: {output_file}")
    try:
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(formatted_content)
    except Exception as exc:
        print(f"❌ 保存失败: {exc}")
        sys.exit(1)

    formatter.print_stats()

    original_size = input_file.stat().st_size
    formatted_size = output_file.stat().st_size
    reduction = (1 - formatted_size / original_size) * 100 if original_size else 0

    print("\n📏 文件大小:")
    print(f"  - 原始: {original_size:,} 字节")
    print(f"  - 格式化后: {formatted_size:,} 字节")
    if reduction > 0:
        print(f"  - 减少: {reduction:.1f}%")
    else:
        print(f"  - 增加: {abs(reduction):.1f}%")

    print(f"\n✅ 完成! 输出文件: {output_file}")


if __name__ == "__main__":
    main()
