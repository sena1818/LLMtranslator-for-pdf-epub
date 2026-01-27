"""
核心翻译引擎
重构自 scripts/async_translator.py
"""
import asyncio
import time
import re
from typing import List, Dict, Optional, Callable
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..utils.config_loader import get_config
from .rate_limiter import RateLimiter
from .output_manager import OutputManager


class TranslationResult:
    """翻译结果"""
    def __init__(self, chunk_index: int, original: str, translation: str,
                 success: bool, retry_count: int = 0, duration: float = 0.0):
        self.chunk_index = chunk_index
        self.original = original
        self.translation = translation
        self.success = success
        self.retry_count = retry_count
        self.duration = duration


class TranslationEngine:
    """异步翻译引擎"""

    def __init__(self, glossary: Dict[str, str] = None):
        """
        初始化翻译引擎

        Args:
            glossary: 术语表字典
        """
        self.config = get_config()
        self.glossary = glossary or {}

        # 初始化 LLM
        self.llm_translator = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.translator_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url
        )

        self.llm_checker = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.checker_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url
        )

        # 初始化组件
        self.rate_limiter = RateLimiter(
            rate=self.config.rate_limit,
            per=60
        )

        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)

    def split_text(self, text: str) -> List[str]:
        """
        智能文本分块

        Args:
            text: 待分块文本

        Returns:
            分块后的文本列表
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=0,
            separators=self.config.get("text_splitting.separators",
                                       ["\n\n", "\n", ".", "!", "?", " ", ""])
        )
        return splitter.split_text(text)

    def clean_output(self, text: str) -> str:
        """
        清理 LLM 输出的废话

        Args:
            text: 原始输出

        Returns:
            清理后的文本
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

        # 删除 markdown 代码块标记
        text = re.sub(r'^```markdown\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        # 清理重复短语 (LLM 循环问题)
        text = self._remove_repetitions(text)

        return text.strip()

    def _remove_repetitions(self, text: str) -> str:
        """
        检测并移除重复短语

        常见的 LLM 重复模式:
        1. 短语连续重复 5+ 次
        2. 句子重复

        Args:
            text: 待处理文本

        Returns:
            清理后的文本
        """
        # 1. 移除连续重复的短语 (5-50字符重复5次以上)
        # 匹配: "某某某某某某某某某某某某" (重复的短语)
        text = re.sub(r'(.{5,50}?)\1{4,}', r'\1', text)

        # 2. 移除连续重复的中文词组 (2-10字重复5次以上)
        text = re.sub(r'([一-龥]{2,10})\1{4,}', r'\1', text)

        # 3. 移除连续重复的英文单词 (重复5次以上)
        text = re.sub(r'\b(\w{3,})\s+(\1\s+){4,}', r'\1 ', text, flags=re.IGNORECASE)

        # 4. 移除连续重复的标点 (如 。。。。。。)
        text = re.sub(r'([。，！？；：])\1{3,}', r'\1\1\1', text)

        return text

    def build_prompt(self, text: str, context: str = "") -> ChatPromptTemplate:
        """
        构建翻译 Prompt

        Args:
            text: 待翻译文本
            context: 上文语境

        Returns:
            Prompt 模板
        """
        template = """你是专业的后现代哲学翻译家,正在翻译学术文本。

【核心术语表】(必须严格遵守):
{glossary}

【上文语境】:
{context}

【待翻译文本】:
{text}

---
【翻译要求】:
1. 完整保留所有 Markdown 格式（标题、加粗、图片、链接、代码块）
2. 风格：学术、精确、保持理论张力
3. 专有名词首次出现时保留英文原文在括号内
4. 严格使用术语表中的译名
5. 直接输出译文，不要任何前言、解释、注释

开始翻译:
"""

        return ChatPromptTemplate.from_template(template)

    async def translate_chunk(
        self,
        chunk_index: int,
        text: str,
        context: str = "",
        progress_callback: Optional[Callable] = None
    ) -> TranslationResult:
        """
        翻译单个文本块

        Args:
            chunk_index: 块索引
            text: 待翻译文本
            context: 上文语境
            progress_callback: 进度回调函数

        Returns:
            翻译结果
        """
        await self.rate_limiter.acquire()

        prompt = self.build_prompt(text, context)
        chain = prompt | self.llm_translator | StrOutputParser()

        # 重试逻辑
        max_retries = self.config.get("api.translator.max_retries", 3)

        for retry in range(max_retries + 1):
            try:
                start_time = time.time()

                translation = await chain.ainvoke({
                    "glossary": "\n".join([f"- {en}: {zh}" for en, zh in self.glossary.items()]),
                    "context": context[-800:] if context else "",
                    "text": text
                })

                # 清理输出
                translation = self.clean_output(translation)

                duration = time.time() - start_time

                # 成功回调
                if progress_callback:
                    await progress_callback({
                        "chunk_index": chunk_index,
                        "status": "completed",
                        "translation": translation,
                        "duration": duration
                    })

                return TranslationResult(
                    chunk_index=chunk_index,
                    original=text,
                    translation=translation,
                    success=True,
                    retry_count=retry,
                    duration=duration
                )

            except Exception as e:
                if retry < max_retries:
                    wait_time = 2 ** retry  # 指数退避
                    await asyncio.sleep(wait_time)
                else:
                    # 失败回调
                    if progress_callback:
                        await progress_callback({
                            "chunk_index": chunk_index,
                            "status": "failed",
                            "error": str(e)
                        })

                    return TranslationResult(
                        chunk_index=chunk_index,
                        original=text,
                        translation=f"[翻译失败: {str(e)}]",
                        success=False,
                        retry_count=retry
                    )

    async def translate_batch(
        self,
        text: str,
        output_path: Path,
        progress_callback: Optional[Callable] = None,
        bilingual: bool = False
    ) -> List[TranslationResult]:
        """
        批量翻译完整文本

        Args:
            text: 完整文本
            output_path: 输出文件路径
            progress_callback: 进度回调
            bilingual: 是否启用双语对照模式

        Returns:
            翻译结果列表
        """
        # 1. 文本分块
        chunks = self.split_text(text)
        total = len(chunks)

        if progress_callback:
            await progress_callback({
                "event": "split_completed",
                "total_chunks": total
            })

        # 2. 创建输出管理器
        output_manager = OutputManager(str(output_path), bilingual=bilingual)

        # 3. 准备任务列表
        tasks = []
        for i, chunk in enumerate(chunks):
            context = chunks[i-1][-500:] if i > 0 else ""
            tasks.append(
                self._process_one_chunk(
                    i, chunk, context, output_manager, progress_callback
                )
            )

        # 4. 并发执行
        results = await asyncio.gather(*tasks)

        return sorted(results, key=lambda r: r.chunk_index)

    async def _process_one_chunk(
        self,
        index: int,
        chunk: str,
        context: str,
        output_manager: OutputManager,
        callback: Optional[Callable]
    ) -> TranslationResult:
        """单块处理(信号量控制)"""
        async with self.semaphore:
            result = await self.translate_chunk(index, chunk, context, callback)

            # 写入输出管理器
            await output_manager.add_result(
                index=result.chunk_index,
                content=result.translation,
                success=result.success,
                original_text=result.original
            )

            return result
