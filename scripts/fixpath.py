import os
import re

# === 这里填你现在那个 "路径不对" 的 Markdown 文件路径 ===
INPUT_FILE = "/Users/sena/Desktop/LLMAgent/translator/output_final/CCRU/Ccru_CN_Final.md"
# === 这里填修复后保存的新文件名 ===
OUTPUT_FILE = "/Users/sena/Desktop/LLMAgent/translator/output_final/Ccru_CN_Relative.md"

def fix_paths(text):
    # 正则逻辑：
    # 寻找任何包含 "/images/" 的路径
    # 比如: /Users/sena/.../images/cover.jpg
    # 替换为: images/cover.jpg

    def replacement(match):
        full_path = match.group(2) # 获取括号里的路径
        if "/images/" in full_path:
            # 只取 'images/' 后面的部分
            relative_path = "images/" + full_path.split("/images/")[-1]
            return f"![{match.group(1)}]({relative_path})"
        return match.group(0)

    # 匹配 markdown 图片语法 ![]()
    return re.sub(r'!\[(.*?)\]\((.*?)\)', replacement, text)

if __name__ == "__main__":
    if os.path.exists(INPUT_FILE):
        print(f"正在读取: {INPUT_FILE} ...")
        with open(INPUT_FILE, encoding='utf-8') as f:
            content = f.read()

        new_content = fix_paths(content)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ 修复完成！\n新文件: {OUTPUT_FILE}")
        print("现在图片路径应该都变成 'images/xxx.jpg' 了。")
    else:
        print("❌ 找不到输入文件，请检查路径是否正确。")
