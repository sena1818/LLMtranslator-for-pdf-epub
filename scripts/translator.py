import os
import json
import time
from typing import List, Dict
from dotenv import load_dotenv

# === 核心库 ===
# 如果报错 ModuleNotFoundError，请运行: pip install langchain-google-genai langchain-text-splitters
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 加载 .env 里的 API Key
load_dotenv()

# === 配置区域 ===
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("请在 .env 文件中填入 GOOGLE_API_KEY！")

# 这里配置你的文件路径
INPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/marker_output/Cyclonopedia/Cyclonopedia.md"  # 你的源文件
OUTPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/output_final/Cyclonopedia_CN.md" # 输出文件
GLOSSARY_PATH = "/Users/sena/Desktop/LLMAgent/translator/glossary.json" # 术语表

# 初始化模型 (推荐使用 Flash 模型，速度快且便宜，适合长文)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3, # 温度低一点，翻译更准确
    google_api_key=API_KEY
)

# === 1. 智能切割器 ===
def split_text(text: str) -> List[str]:
    """
    不管原文 # 号乱不乱，我们强制按字符数智能切割。
    chunk_size=2000: 每次翻译大约 1000-1500 个汉字的量，最稳。
    chunk_overlap=200: 保留重叠，防止上下文断裂。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""] # 优先按段落切
    )
    return splitter.split_text(text)

# === 2. 翻译函数 ===
def translate_chunk(text: str, glossary: Dict, context: str) -> str:
    prompt_template = """
    你是一位精通后现代哲学、克苏鲁神话与地缘政治的专业翻译家。
    你正在翻译 Reza Negarestani 的著作《Cyclonopedia》。

    【核心术语表】(请严格遵守):
    {glossary}

    【上文语境】(仅供参考语气):
    {context}

    【待翻译文本】:
    {text}

    ---
    【翻译要求】:
    1. **保留 Markdown 格式**：不要丢失标题(#)、加粗(**)、图片链接(![])。
    2. **风格**：学术、晦涩、带有各种“理论虚构”的恐怖感。不要把句子改得太通俗。
    3. **专有名词**：首次出现时保留英文原名在括号内。
    4. **直接输出译文**：不要输出“好的”、“以下是翻译”等废话。
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()
    
    try:
        return chain.invoke({
            "glossary": json.dumps(glossary, ensure_ascii=False),
            "context": context[-500:], # 只看最近 500 字符
            "text": text
        })
    except Exception as e:
        print(f"Error translating chunk: {e}")
        time.sleep(5) # 报错稍微等一下
        return text # 降级处理：如果失败返回原文，避免程序崩溃

# === 主程序 ===
def main():
    print(f"📖 读取文件: {INPUT_PATH} ...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        full_text = f.read()

    # 读取术语表
    glossary = {}
    if os.path.exists(GLOSSARY_PATH):
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            glossary = json.load(f)
            print(f"📚 加载术语表: 包含 {len(glossary)} 个词条")

    # 切割文本
    chunks = split_text(full_text)
    print(f"✂️ 文本已切割为 {len(chunks)} 个块。准备开始翻译...")

    # 准备输出文件（清空旧的）
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("> 本书由 AI Agent 自动翻译\n\n")

    last_context = "书籍开篇。"

    # 循环翻译
    for i, chunk in enumerate(chunks):
        print(f"🚀 [进度 {i+1}/{len(chunks)}] 正在翻译...")
        
        translation = translate_chunk(chunk, glossary, last_context)
        
        # 实时写入文件（防止死机白跑）
        with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
            f.write(translation + "\n\n")
            
        # 更新上下文
        last_context = translation
        
        # 稍微休息一下，避免触发 API 频率限制
        time.sleep(5)

    print(f"✅ 翻译完成！文件已保存至: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()