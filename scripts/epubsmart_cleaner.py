import re
import os

# === 配置你的文件路径 ===
INPUT_FILE = "/Users/sena/Desktop/LLMAgent/translator/output_final/Ccru_CN_ASYNC.md"
OUTPUT_FILE = "/Users/sena/Desktop/LLMAgent/translator/output_final/Ccru_CN_Cleaned.md"

def smart_format_conversion(text: str) -> str:
    """
    将 Pandoc 的残留标记转换为 Markdown 格式
    """
    
    # 1. === 处理封面图 (SVG 转换) ===
    # 原文: <image ... xlink:href="images/cover.jpg">...</image>
    # 目标: ![](images/cover.jpg)
    def extract_cover(match):
        # 提取 href 里的路径
        img_path = re.search(r'xlink:href="([^"]+)"', match.group(0))
        if img_path:
            return f'\n\n![]({img_path.group(1)})\n\n'
        return ""
    
    # 匹配整个 SVG 块
    text = re.sub(r'<svg.*?</svg>', extract_cover, text, flags=re.DOTALL)
    text = re.sub(r'::: \{\}\s*!\[\].*?:::', '', text, flags=re.DOTALL) # 清理残留的空图片容器

    # 2. === 处理标题映射 (根据你的截图观察) ===
    # 逻辑：[.calibre2] 通常是书名或大标题 -> 转换成 # (H1)
    text = re.sub(r'\[(.*?)\]\{\.calibre2\}', r'# \1', text)
    
    # 逻辑：[.calibre3] 通常是章节名 -> 转换成 ## (H2)
    text = re.sub(r'\[(.*?)\]\{\.calibre3\}', r'## \1', text)
    
    # 逻辑：[.calibre4] 或其他 -> 转换成 **加粗**
    text = re.sub(r'\[(.*?)\]\{\.calibre[4-9]\}', r'**\1**', text)
    
    # 3. === 处理分页符 ===
    # 原文: ::: { ... .mbp_pagebreak } :::
    # 目标: --- (Markdown 分割线)
    text = re.sub(r'^:::\s*\{.*?pagebreak.*?\}\s*$', r'\n---\n', text, flags=re.MULTILINE)
    
    # 4. === 清理剩余的垃圾标记 ===
    # 处理剩下的 [文字]{.calibre1} -> 纯文字 (calibre1 通常是正文)
    text = re.sub(r'\[(.*?)\]\{[^}]+\}', r'\1', text)
    
    # 清理剩下的 ::: 块
    text = re.sub(r'^:::\s*\{.*?\}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^:::\s*$', '', text, flags=re.MULTILINE)
    
    # 清理 HTML 残留
    text = re.sub(r'\{=html\}', '', text)
    text = re.sub(r'\[\]\{#.*?\}', '', text) # 清理锚点 []{#index...}

    # 5. === 格式美化 ===
    # 去除多余空行 (超过3行变2行)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

# === 执行转换 ===
if os.path.exists(INPUT_FILE):
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    cleaned_content = smart_format_conversion(content)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
        
    print(f"✅ 转换完成！\n输入: {INPUT_FILE}\n输出: {OUTPUT_FILE}")
    print("现在所有的 {.calibre} 都应该变成了标题或正文。")
else:
    print("❌ 找不到输入文件，请检查路径。")