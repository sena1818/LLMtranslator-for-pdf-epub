#!/bin/bash
#
# 自动化格式处理流水线
# 用于处理 Pandoc 从 EPUB 转换后的 Markdown 文件
#
# 使用方法:
#   ./scripts/auto_format_pipeline.sh input.md output.md
#

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -lt 1 ]; then
    echo -e "${RED}用法: $0 <input_file> [output_file]${NC}"
    echo ""
    echo "示例:"
    echo "  $0 data/temp/book.md"
    echo "  $0 data/temp/book.md data/output/book_formatted.md"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="${2:-${INPUT_FILE%.md}_formatted.md}"

# 检查输入文件是否存在
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}❌ 错误: 文件不存在: $INPUT_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}   自动化 Markdown 格式处理流水线${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# 步骤 1: 智能格式化
echo -e "${YELLOW}📝 步骤 1/3: 智能格式化 (保留目录,转换格式)${NC}"
TEMP_FILE_1="${INPUT_FILE%.md}_step1.md"
python scripts/smart_markdown_formatter.py "$INPUT_FILE" "$TEMP_FILE_1"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 步骤 1 失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 步骤 1 完成${NC}"
echo ""

# 步骤 2: 修复图片路径 (如果存在图片)
echo -e "${YELLOW}🖼️  步骤 2/3: 修复图片路径${NC}"
if grep -q "!\[.*\](.*images.*)" "$TEMP_FILE_1" 2>/dev/null; then
    TEMP_FILE_2="${INPUT_FILE%.md}_step2.md"
    python scripts/fixpath.py "$TEMP_FILE_1" "$TEMP_FILE_2" 2>/dev/null || cp "$TEMP_FILE_1" "$TEMP_FILE_2"
    echo -e "${GREEN}✅ 图片路径已修复${NC}"
else
    echo -e "${BLUE}ℹ️  未检测到图片,跳过此步骤${NC}"
    TEMP_FILE_2="$TEMP_FILE_1"
fi
echo ""

# 步骤 3: 最终清理 (移除剩余的杂项)
echo -e "${YELLOW}🧹 步骤 3/3: 最终清理${NC}"
# 使用 sed 进行最后的清理
cat "$TEMP_FILE_2" | \
    sed 's/\\\[/[/g' | \
    sed 's/\\\]/]/g' | \
    sed 's/\[ \]/[]/g' | \
    sed '/^$/N;/^\n$/d' > "$OUTPUT_FILE"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 步骤 3 失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 步骤 3 完成${NC}"
echo ""

# 清理临时文件
rm -f "$TEMP_FILE_1" "$TEMP_FILE_2"
echo -e "${BLUE}🗑️  临时文件已清理${NC}"
echo ""

# 显示结果
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 处理完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}输入文件:${NC} $INPUT_FILE"
echo -e "${BLUE}输出文件:${NC} $OUTPUT_FILE"
echo ""

# 文件大小对比
INPUT_SIZE=$(wc -c < "$INPUT_FILE" | xargs)
OUTPUT_SIZE=$(wc -c < "$OUTPUT_FILE" | xargs)
REDUCTION=$(echo "scale=1; (1 - $OUTPUT_SIZE / $INPUT_SIZE) * 100" | bc)

echo -e "${BLUE}文件大小:${NC}"
echo -e "  原始: $(numfmt --to=iec-i --suffix=B $INPUT_SIZE 2>/dev/null || echo "$INPUT_SIZE bytes")"
echo -e "  处理后: $(numfmt --to=iec-i --suffix=B $OUTPUT_SIZE 2>/dev/null || echo "$OUTPUT_SIZE bytes")"
echo -e "  减少: ${REDUCTION}%"
echo ""

# 预览前10行
echo -e "${BLUE}📄 预览 (前10行):${NC}"
echo -e "${YELLOW}$(head -10 "$OUTPUT_FILE")${NC}"
echo ""

echo -e "${GREEN}🎉 大功告成!${NC}"
