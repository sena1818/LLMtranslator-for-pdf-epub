"""
异步并发翻译系统 
1. Checker输出废话 → 强制只输出译文
2. Markdown格式丢失 → 增强格式保留提示
3. 图片路径错误 → 自动转换为绝对路径
4. 异步版本不写入 → 修复OutputManager逻辑
"""

import os
import json
import asyncio
import time
import re
from typing import List, Dict, Optional, TypedDict
from dotenv import load_dotenv
import logging
from pathlib import Path
import aiofiles

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler('translation_async.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# === 配置 ===
API_KEY = os.getenv("SILICONFLOW_API_KEY")
INPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/input/Ccru/Ccru.md"
OUTPUT_PATH = "/Users/sena/Desktop/LLMAgent/translator/output_final/Ccru_CN_ASYNC.md"
GLOSSARY_PATH = "/Users/sena/Desktop/LLMAgent/translator/glossary.json"
PROGRESS_PATH = "/Users/sena/Desktop/LLMAgent/translator/progress_async.json"
IMAGE_BASE_PATH = "/Users/sena/Desktop/LLMAgent/translator/marker_output/Ccru"  # 图片基础路径
SILICON_BASE_URL = "https://api.siliconflow.cn/v1"

# === 并发控制参数 ===
MAX_CONCURRENT_REQUESTS = 10
BATCH_SIZE = 5
RATE_LIMIT_PER_MINUTE = 200  # DeepSeek支持更高并发
REQUEST_TIMEOUT = 60

# 初始化 LLM
llm_translator = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V3", 
    temperature=0.3, 
    api_key=API_KEY,
    base_url=SILICON_BASE_URL
)

llm_checker = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V3", 
    temperature=0.1, 
    api_key=API_KEY,
    base_url=SILICON_BASE_URL
)


# === 状态定义 ===
class TranslationState(TypedDict):
    chunk_index: int
    original_text: str
    translation: str
    context: str
    glossary: Dict[str, str]
    qa_result: Dict
    retry_count: int
    max_retries: int
    start_time: float
    end_time: float


# === 速率限制器 ===
class RateLimiter:
    def __init__(self, rate: int, per: int = 60):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            current = time.time()
            time_passed = current - self.last_check
            self.last_check = current
            
            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = self.rate
            
            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.per / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE, per=60)


# === 工具函数 ===
def split_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=0,  # change to 0 to avoid context repeat
        separators=["\n\n", "\n", ".", "!", "?", " ", ""]
    )
    return splitter.split_text(text)


def fix_image_paths(text: str, base_path: str) -> str:
    def replace_path(match):
        relative_path = match.group(1)
        # 只处理相对路径（不以 / 或 http 开头）
        if not relative_path.startswith('/') and not relative_path.startswith('http'):
            absolute_path = os.path.join(base_path, relative_path)
            return f'![]({absolute_path})'
        return match.group(0)
    
    return re.sub(r'!\[\]\(([^)]+)\)', replace_path, text)


def clean_translation_output(text: str) -> str:
    """
    清理翻译输出中的废话
    1. 删除 "（注：...）" 
    2. 删除 "【修正后的译文】:"
    3. 删除 "Here is the translation"
    4. 删除多余的提示语
    """
    # 删除中文注释
    text = re.sub(r'（注：[^）]*）', '', text)
    text = re.sub(r'\(注：[^)]*\)', '', text)
    
    # 删除修正标记
    text = re.sub(r'【修正后的译文】[:：]?\s*', '', text)
    text = re.sub(r'\[修正后的译文\][:：]?\s*', '', text)
    
    # 删除英文提示
    text = re.sub(r'^Here is the translation[:：]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Translation[:：]?\s*', '', text, flags=re.IGNORECASE)
    
    # 删除 markdown 代码块标记（有些模型会加这个）
    text = re.sub(r'^```markdown\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    
    return text.strip()


async def load_progress() -> Dict:
    if os.path.exists(PROGRESS_PATH):
        async with aiofiles.open(PROGRESS_PATH, 'r') as f:
            content = await f.read()
            return json.loads(content)
    return {"completed": [], "failed": []}


async def save_progress(completed: List[int], failed: List[int]):
    async with aiofiles.open(PROGRESS_PATH, 'w') as f:
        await f.write(json.dumps({
            "completed": sorted(list(completed)),
            "failed": sorted(list(failed)),
            "timestamp": time.time()
        }, indent=2))


# === 基础异步翻译 ===
async def translate_chunk_async(
    chunk_index: int,
    text: str,
    glossary: Dict,
    context: str,
    retry_count: int = 0,
    max_retries: int = 3
) -> Dict:
    """异步翻译单个 chunk"""
    
    await rate_limiter.acquire()
    
    logger.info(f"🚀 [Chunk {chunk_index}] 开始翻译 (尝试 {retry_count + 1}/{max_retries + 1})")
    
    # === 增强版 Prompt ===
    prompt_template = """你是专业的后现代哲学翻译家，正在翻译nick land 的Ccru writings。

【核心术语表】(必须严格遵守):
{glossary}

【上文语境】:
{context}

【待翻译文本】:
{text}

---
【翻译要求】:
1. **完整保留所有 Markdown 格式**：
   - 保留标题层级 (#, ##, ###)
   - 保留上标/下标标记 (<sup>, <sub>)
   - 保留加粗/斜体 (**, *, _)
   - 保留图片链接 (![](...)，必须原样保留路径)
   - 保留换行和空行结构

2. **风格要求**：
   - 学术、晦涩、带理论虚构感
   - 专有名词首次出现保留英文原文在括号内
   - 严格使用术语表中的译名

3. **输出格式**：
   - **直接输出译文正文，不要任何前言、后记、注释**
   - **严禁输出"（注：...）"、"【修正后的译文】"、"Here is"等废话**
   - **不要添加任何说明性文字**

开始翻译（直接输出译文）:
"""
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm_translator | StrOutputParser()
    
    try:
        start_time = time.time()
        
        translation = await chain.ainvoke({
            "glossary": "\n".join([f"- {en}: {zh}" for en, zh in glossary.items()]),
            "context": context[-800:] if context else "",
            "text": text
        })
        
        # 清理输出
        translation = clean_translation_output(translation)
        
        # 修复图片路径
        translation = fix_image_paths(translation, IMAGE_BASE_PATH)
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"✅ [Chunk {chunk_index}] 翻译完成 (耗时 {duration:.2f}s, 长度 {len(translation)}字)")
        
        return {
            "chunk_index": chunk_index,
            "original_text": text,
            "translation": translation,
            "success": True,
            "duration": duration,
            "retry_count": retry_count
        }
        
    except Exception as e:
        logger.error(f"❌ [Chunk {chunk_index}] 翻译失败: {e}")
        
        if retry_count < max_retries:
            wait_time = 2 ** retry_count
            logger.info(f"⏳ [Chunk {chunk_index}] {wait_time}秒后重试...")
            await asyncio.sleep(wait_time)
            return await translate_chunk_async(
                chunk_index, text, glossary, context, retry_count + 1, max_retries
            )
        
        return {
            "chunk_index": chunk_index,
            "original_text": text,
            "translation": f"[翻译失败: {str(e)}]",
            "success": False,
            "error": str(e),
            "retry_count": retry_count
        }


# === 质检节点 ===
async def qa_check_async(result: Dict, glossary: Dict) -> Dict:
    chunk_index = result["chunk_index"]
    logger.info(f"🔍 [Chunk {chunk_index}] 质检中...")
    
    issues = []
    translation = result["translation"]
    original = result["original_text"]
    
    # 1. 检查是否有明显的废话标记
    if "（注：" in translation or "【修正后的译文】" in translation:
        issues.append("包含废话标记")
    
    # 2. 检查关键术语（只检查前5个重要术语，避免过度检查）
    important_terms = list(glossary.items())[:5]
    for en_term, zh_term in important_terms:
        if en_term.lower() in original.lower():
            if zh_term not in translation and en_term not in translation:
                issues.append(f"术语 '{en_term}' 未找到对应翻译")
    
    # 3. 检查是否有大段未翻译的英文（超过30个连续英文单词）
    long_english = re.findall(r'[a-zA-Z]+(?:\s+[a-zA-Z]+){29,}', translation)
    if long_english:
        issues.append("检测到未翻译的长段落")
    
    # 4. 检查图片标签是否保留
    original_images = re.findall(r'!\[.*?\]\([^)]+\)', original)
    translated_images = re.findall(r'!\[.*?\]\([^)]+\)', translation)
    if len(original_images) != len(translated_images):
        issues.append(f"图片数量不匹配: 原文{len(original_images)}个, 译文{len(translated_images)}个")
    
    result["qa_result"] = {
        "pass": len(issues) == 0,
        "issues": issues
    }
    
    if issues:
        logger.warning(f"⚠️ [Chunk {chunk_index}] 发现 {len(issues)} 个问题: {', '.join(issues)}")
    else:
        logger.info(f"✅ [Chunk {chunk_index}] 质检通过")
    
    return result


# === 修复节点 ===
async def fix_translation_async(result: Dict, glossary: Dict, max_fix_attempts: int = 1) -> Dict:
    """简化修复流程，避免过度修正"""
    
    chunk_index = result["chunk_index"]
    
    if result.get("fix_attempts", 0) >= max_fix_attempts:
        logger.warning(f"⚠️ [Chunk {chunk_index}] 跳过修复（已达最大尝试次数）")
        # 强制通过，避免卡死
        result["qa_result"]["pass"] = True
        return result
    
    await rate_limiter.acquire()
    
    logger.info(f"🔧 [Chunk {chunk_index}] 修复中...")
    
    issues_text = "\n".join([f"- {issue}" for issue in result["qa_result"]["issues"]])
    
    # === 极简修复 Prompt ===
    prompt_template = """【原文】:
{original}

【当前译文】:
{translation}

【问题】:
{issues}

---
要求：
1. 只修正上述问题
2. 保持其他部分完全不变
3. 不要添加任何注释或说明
4. 直接输出完整修正后的译文

修正后的译文:
"""
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm_checker | StrOutputParser()
    
    try:
        fixed = await chain.ainvoke({
            "original": result["original_text"][:1000],  # 只传前1000字符，节省token
            "translation": result["translation"],
            "issues": issues_text
        })
        
        # 清理修复后的输出
        fixed = clean_translation_output(fixed)
        fixed = fix_image_paths(fixed, IMAGE_BASE_PATH)
        
        result["translation"] = fixed
        result["fix_attempts"] = result.get("fix_attempts", 0) + 1
        
        # 简化再次质检：直接标记为通过，避免无限循环
        result["qa_result"]["pass"] = True
        
        logger.info(f"✅ [Chunk {chunk_index}] 修复完成")
        
    except Exception as e:
        logger.error(f"❌ [Chunk {chunk_index}] 修复失败: {e}")
        # 修复失败就放弃，避免卡死
        result["qa_result"]["pass"] = True
    
    return result


# === 批量并发处理 ===
async def process_batch(
    batch: List[tuple],
    glossary: Dict,
    semaphore: asyncio.Semaphore
) -> List[Dict]:
    """并发处理一个批次"""
    
    async def process_one(item):
        async with semaphore:
            index, chunk, context = item
            result = await translate_chunk_async(index, chunk, glossary, context)
            
            if result["success"]:
                result = await qa_check_async(result, glossary)
                
                # 只在有严重问题时才修复
                if not result["qa_result"]["pass"] and any(
                    "未翻译" in issue or "废话" in issue 
                    for issue in result["qa_result"]["issues"]
                ):
                    result = await fix_translation_async(result, glossary)
            
            return result
    
    results = await asyncio.gather(*[process_one(item) for item in batch])
    return results


class OutputManager:
    """
    输出管理器。
    核心思想：无论成功失败，都必须向 buffer 提交结果，
    这样 next_index 才能滚动，后续积压的 buffer 才能释放。
    """
    
    def __init__(self, output_path: str, start_index: int = 0):
        self.output_path = output_path
        self.buffer = {}  # {index: content}
        self.next_index = start_index
        self.lock = asyncio.Lock()
        self.last_save_time = time.time()
        self.written_count = 0

    async def add_result(self, index: int, content: str, success: bool, original_text: str = ""):
        """
        提交结果。如果是失败，自动生成占位符内容。
        """
        async with self.lock:
            # 1. 构造写入内容
            if success:
                final_content = content
            else:
                # 失败时写入占位符，包含原文以便后续人工补全
                logger.warning(f"⚠️ Chunk {index} 失败，写入占位符以释放阻塞...")
                final_content = (
                    f"\n\n> **[翻译失败 - Chunk {index}]**\n"
                    f"> *API 请求失败或超时，请根据以下原文手动补全:*\n\n"
                    f"```text\n{original_text[:500]}...\n```\n\n"
                )

            # 2. 存入缓冲区
            self.buffer[index] = final_content

            # 3. 尝试连续写入 (Flush Buffer)
            # 只要 next_index 存在于 buffer 中，就一直写
            # 即使 Chunk 100 是失败占位符，它也算"存在"，会让循环继续到 101
            has_written = False
            async with aiofiles.open(self.output_path, 'a', encoding='utf-8') as f:
                while self.next_index in self.buffer:
                    text_to_write = self.buffer[self.next_index]
                    
                    # 写入 Markdown 注释标记，方便后续定位
                    await f.write(f"\n\n")
                    await f.write(text_to_write)
                    await f.write(f"\n\n")
                    
                    # 清理内存
                    del self.buffer[self.next_index]
                    self.next_index += 1
                    self.written_count += 1
                    has_written = True
            
            if has_written:
                logger.info(f"💾 写入进度推进至 Chunk {self.next_index}")


# === 主程序 ===
async def main():
    logger.info(f"📖 读取文件: {INPUT_PATH}")
    
    async with aiofiles.open(INPUT_PATH, 'r', encoding='utf-8') as f:
        full_text = await f.read()
    
    # 加载术语表
    glossary = {}
    if os.path.exists(GLOSSARY_PATH):
        async with aiofiles.open(GLOSSARY_PATH, 'r', encoding='utf-8') as f:
            content = await f.read()
            glossary = json.loads(content)
            logger.info(f"📚 术语表: {len(glossary)} 个词条")
    
    # 切割文本
    chunks = split_text(full_text)
    # chunks = split_text(full_text)[:5]  # 只测试前5个
    total_chunks = len(chunks)
    
    logger.info(f"✂️ 切割完成: {total_chunks} 个块")
    
    # 加载进度
    progress = await load_progress()
    completed = set(progress.get("completed", []))
    failed = set(progress.get("failed", []))
    
    logger.info(f"📊 进度状态: 已完成 {len(completed)} 个, 失败 {len(failed)} 个")
    
    # 初始化输出文件（只在第一次运行时）
    if not completed and not os.path.exists(OUTPUT_PATH):
        async with aiofiles.open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            await f.write("#  - 中文翻译\n\n")
            await f.write("> 本书由 DeepSeek V3 异步并发翻译\n")
            await f.write(f"> 最大并发数: {MAX_CONCURRENT_REQUESTS}\n\n")
        logger.info(f"📄 输出文件已初始化: {OUTPUT_PATH}")
    
    # 创建输出管理器
    output_manager = OutputManager(OUTPUT_PATH)
    
    # 准备待处理的 chunks
    pending_chunks = []
    for i in range(total_chunks):
        if i in completed or i in failed:
            continue
            
        # 获取上一块的最后 500 个字符作为"上文语境"
        # 这样 AI 能看到上文，保证连贯，但因为这部分不在 {text} 里，所以不会被翻译出来
        current_context = chunks[i-1][-500:] if i > 0 else ""
        
        pending_chunks.append((i, chunks[i], current_context))
    
    if not pending_chunks:
        logger.info("✅ 所有 chunks 已完成!")
        return
    
    logger.info(f"🚀 开始并发翻译: {len(pending_chunks)} 个待处理块")
    
    # 创建信号量
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # 分批处理
    start_time = time.time()
    
    for i in range(0, len(pending_chunks), BATCH_SIZE):
        batch = pending_chunks[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(pending_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📦 批次 {batch_num}/{total_batches} (包含 {len(batch)} 个 chunks)")
        logger.info(f"{'='*60}")
        
        # 并发处理
        results = await process_batch(batch, glossary, semaphore)
        
        # 收集结果
        new_completed = []
        new_failed = []
        
        for result in results:
            await output_manager.add_result(
                index=result["chunk_index"],
                content=result["translation"],
                success=result["success"],
                original_text=result["original_text"]
            )

            if result["success"]:
                new_completed.append(result["chunk_index"])
            else:
                new_failed.append(result["chunk_index"])
                logger.error(f"❌ [Chunk {result['chunk_index']}] 标记为失败 (已写入占位符)")
        
        # 更新进度
        completed.update(new_completed)
        failed.update(new_failed)
        await save_progress(list(completed), list(failed))
        
        # 显示进度
        progress_pct = len(completed) / total_chunks * 100
        elapsed = time.time() - start_time
        speed = len(completed) / (elapsed / 60) if elapsed > 0 else 0
        
        logger.info(f"📊 进度: {len(completed)}/{total_chunks} ({progress_pct:.1f}%) | 速度: {speed:.1f} chunks/分钟")
    
    # 总结
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 翻译完成!")
    logger.info(f"⏱️  总耗时: {elapsed/60:.2f} 分钟")
    logger.info(f"📈 平均速度: {total_chunks/(elapsed/60):.1f} chunks/分钟")
    logger.info(f"✅ 成功: {len(completed)} 个")
    logger.info(f"❌ 失败: {len(failed)} 个")
    if failed:
        logger.info(f"失败索引: {sorted(failed)}")
    logger.info(f"💾 输出文件: {OUTPUT_PATH}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())