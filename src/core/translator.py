"""
核心翻译引擎
重构自 scripts/async_translator.py
"""
import asyncio
import json
import logging
import time
import re
import hashlib
from typing import List, Dict, Optional, Callable
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..utils.config_loader import get_config
from ..utils.prompt_library import PromptLibrary
from .chunk_planner import ChunkPlanner, TextChunk
from .rate_limiter import RateLimiter
from .translation_cache import TranslationCache
from .validator import QualityReport, TranslationValidator
from ..domain.models.translation_models import DocumentProfile, TranslationResult


logger = logging.getLogger(__name__)


class TranslationEngine:
    """异步翻译引擎"""

    def __init__(self, glossary: Dict[str, str] = None, domain: str = None):
        """
        初始化翻译引擎

        Args:
            glossary: 术语表字典
            domain: 翻译体裁（决定加载哪套 Prompt 模板），缺省读配置
        """
        self.config = get_config()
        self.glossary = glossary or {}
        self.domain = domain or self.config.domain
        self.prompt_library = PromptLibrary(
            self.config.prompts_dir, default_domain="philosophy"
        )

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
        self.llm_analyst = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.analyst_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url
        )

        # 初始化组件
        self.rate_limiter = RateLimiter(
            rate=self.config.rate_limit,
            per=60
        )

        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self.chunk_planner = ChunkPlanner(
            chunk_size=self.config.chunk_size,
            context_window=self.config.context_window,
            target_chunk_size=self.config.target_chunk_size,
            min_chunk_size=self.config.min_chunk_size,
        )
        self.validator = TranslationValidator(
            untranslated_word_span=self.config.untranslated_word_span,
            max_glossary_checks=self.config.max_glossary_checks,
        )
        self.cache = TranslationCache(self.config.root_dir / "data" / "translation_cache.db")
        self.document_profile = DocumentProfile.empty()
        self.prompt_version = "v3"

    def plan_chunks(self, text: str) -> List[TextChunk]:
        """结构化切块"""
        return self.chunk_planner.plan(text)

    def split_text(self, text: str) -> List[str]:
        """
        智能文本分块

        Args:
            text: 待分块文本

        Returns:
            分块后的文本列表
        """
        return [chunk.text for chunk in self.plan_chunks(text)]

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

    def build_prompt(self, chunk: TextChunk, document_profile: Optional[DocumentProfile] = None) -> ChatPromptTemplate:
        """
        构建翻译 Prompt

        Args:
            chunk: 待翻译文本块
            document_profile: 文档级分析信息

        Returns:
            Prompt 模板
        """
        template = self.prompt_library.translator_template(self.domain)
        return ChatPromptTemplate.from_template(template)

    async def analyze_document(
        self,
        text: str,
        chunks: List[TextChunk],
    ) -> DocumentProfile:
        """文档分析 agent：提炼整本文档的风格与术语上下文"""
        if not getattr(self.config, "multi_agent_enabled", False):
            return DocumentProfile.empty()

        unique_sections = []
        for chunk in chunks:
            title = " > ".join(chunk.section_path) if chunk.section_path else chunk.section_title
            if title and title not in unique_sections:
                unique_sections.append(title)
            if len(unique_sections) >= self.config.analyst_max_sections:
                break

        excerpt = text[: self.config.analyst_max_chars]
        analyst_prompt = ChatPromptTemplate.from_template(
            """你是翻译团队中的“文档分析员”。请基于以下文档片段和章节信息，为后续翻译提供全局指导。

输出必须是 JSON 对象，格式如下：
{{
  "summary": "一句到三句的文档摘要",
  "style_notes": ["风格提示1", "风格提示2"],
  "terminology_hints": ["术语提示1", "术语提示2"],
  "section_overview": ["章节1", "章节2"]
}}

要求：
1. 不要输出 JSON 以外的任何文字
2. style_notes 最多 4 条
3. terminology_hints 最多 {max_term_hints} 条
4. section_overview 只保留最关键的章节线索

【章节列表】:
{sections}

【文档片段】:
{excerpt}
"""
        )
        chain = analyst_prompt | self.llm_analyst | StrOutputParser()

        try:
            raw = await asyncio.wait_for(
                chain.ainvoke(
                    {
                        "max_term_hints": getattr(self.config, "analyst_max_term_hints", 12),
                        "sections": "\n".join(f"- {item}" for item in unique_sections) or "- Document Root",
                        "excerpt": excerpt,
                    }
                ),
                timeout=self.config.request_timeout,
            )
            return self._parse_document_profile(raw)
        except Exception as exc:
            logger.warning("文档分析 agent 失败，退化为空 profile: %s", exc)
            return DocumentProfile.empty()

    def _parse_document_profile(self, raw: str) -> DocumentProfile:
        """解析文档分析 agent 返回的 JSON"""
        try:
            payload_text = raw.strip()
            if not payload_text.startswith("{"):
                match = re.search(r"\{[\s\S]*\}", payload_text)
                if match:
                    payload_text = match.group(0)
            data = json.loads(payload_text)
        except Exception as exc:
            logger.warning("文档分析结果解析失败，退化为空 profile: %s", exc)
            return DocumentProfile.empty()

        return DocumentProfile(
            summary=str(data.get("summary", "")).strip(),
            style_notes=[str(item).strip() for item in data.get("style_notes", []) if str(item).strip()][:4],
            terminology_hints=[
                str(item).strip()
                for item in data.get("terminology_hints", [])
                if str(item).strip()
            ][: getattr(self.config, "analyst_max_term_hints", 12)],
            section_overview=[
                str(item).strip() for item in data.get("section_overview", []) if str(item).strip()
            ][: getattr(self.config, "analyst_max_sections", 12)],
        )

    def _build_cache_key(self, chunk: TextChunk) -> str:
        """构造缓存键，避免不同模型/术语表之间串用"""
        glossary_payload = "\n".join(
            f"{en}:{zh}" for en, zh in sorted(self.glossary.items())
        )
        payload = "|".join(
            [
                self.prompt_version,
                getattr(self, "domain", "") or "",
                self.config.model_name or "",
                chunk.chunk_id,
                self.document_profile.fingerprint,
                glossary_payload,
            ]
        ).encode("utf-8")
        return hashlib.sha1(payload).hexdigest()

    async def translate_chunk(
        self,
        chunk: TextChunk,
        progress_callback: Optional[Callable] = None
    ) -> TranslationResult:
        """
        翻译单个文本块

        Args:
            chunk: 结构化文本块
            progress_callback: 进度回调函数

        Returns:
            翻译结果
        """
        await self.rate_limiter.acquire()

        prompt = self.build_prompt(chunk, self.document_profile)
        chain = prompt | self.llm_translator | StrOutputParser()

        # 重试逻辑
        max_retries = self.config.get("api.translator.max_retries", 3)

        for retry in range(max_retries + 1):
            try:
                start_time = time.time()

                translation = await asyncio.wait_for(
                    chain.ainvoke({
                        "document_profile": self.document_profile.to_prompt_text(),
                        "glossary": "\n".join([f"- {en}: {zh}" for en, zh in self.glossary.items()]),
                        "section_title": " > ".join(chunk.section_path) if chunk.section_path else chunk.section_title,
                        "context": chunk.context_text,
                        "text": chunk.text
                    }),
                    timeout=self.config.request_timeout,
                )

                # 清理输出
                translation = self.clean_output(translation)
                translation, quality_report, repaired = await self._run_quality_pipeline(
                    chunk=chunk,
                    translation=translation,
                )

                duration = time.time() - start_time

                # 成功回调
                if progress_callback:
                    await progress_callback({
                        "chunk_index": chunk.index,
                        "chunk_id": chunk.chunk_id,
                        "status": "completed",
                        "translation": translation,
                        "duration": duration,
                        "quality_report": quality_report.to_dict(),
                        "repaired": repaired,
                        "cached": False,
                    })

                await self.cache.set(
                    cache_key=self._build_cache_key(chunk),
                    chunk_id=chunk.chunk_id,
                    translation=translation,
                    quality_report=quality_report.to_dict(),
                    repaired=repaired,
                )

                return TranslationResult(
                    chunk_index=chunk.index,
                    original=chunk.text,
                    translation=translation,
                    success=True,
                    retry_count=retry,
                    duration=duration,
                    chunk_id=chunk.chunk_id,
                    quality_report=quality_report.to_dict(),
                    repaired=repaired,
                    cached=False,
                )

            except Exception as e:
                if retry < max_retries:
                    wait_time = 2 ** retry  # 指数退避
                    await asyncio.sleep(wait_time)
                else:
                    # 失败回调
                    if progress_callback:
                        await progress_callback({
                            "chunk_index": chunk.index,
                            "chunk_id": chunk.chunk_id,
                            "status": "failed",
                            "error": str(e)
                        })

                    return TranslationResult(
                        chunk_index=chunk.index,
                        original=chunk.text,
                        translation=f"[翻译失败: {str(e)}]",
                        success=False,
                        retry_count=retry,
                        chunk_id=chunk.chunk_id,
                        quality_report={"passed": False, "issue_count": 1, "issues": []},
                    )

    async def _run_quality_pipeline(
        self,
        chunk: TextChunk,
        translation: str,
    ) -> tuple[str, QualityReport, bool]:
        """质量检查与选择性修复"""
        if not self.config.enable_qa_check:
            return translation, QualityReport(passed=True), False

        baseline = self.validator.validate(chunk.text, translation, self.glossary)
        if baseline.passed or not self.validator.should_repair(baseline):
            return translation, baseline, False

        best_translation = translation
        best_report = baseline
        repaired = False

        for _ in range(self.config.max_fix_attempts):
            candidate_translation = await self._repair_translation(
                chunk=chunk,
                translation=best_translation,
                report=best_report,
            )
            candidate_translation = self.clean_output(candidate_translation)
            candidate_report = self.validator.validate(chunk.text, candidate_translation, self.glossary)

            if self.validator.is_better(candidate_report, best_report):
                best_translation = candidate_translation
                best_report = candidate_report
                repaired = True

            if best_report.passed:
                break

        return best_translation, best_report, repaired

    async def _repair_translation(
        self,
        chunk: TextChunk,
        translation: str,
        report: QualityReport,
    ) -> str:
        """对高风险 chunk 触发一次修复"""
        await self.rate_limiter.acquire()

        issues_text = "\n".join(f"- {issue.message}" for issue in report.issues)
        prompt_template = """你是学术翻译审校者。请在不改变原意和 Markdown 结构的前提下修正译文。

【章节】:
{section_title}

【原文】:
{original}

【当前译文】:
{translation}

【发现的问题】:
{issues}

【文档分析员备忘】:
{document_profile}

【术语表】(必须严格遵守):
{glossary}

---
要求：
1. 只修正问题相关部分
2. 保留标题、链接、图片、代码块、引用块
3. 不要添加说明或注释
4. 直接输出修正后的完整译文
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm_checker | StrOutputParser()

        return await asyncio.wait_for(
            chain.ainvoke({
                "section_title": " > ".join(chunk.section_path) if chunk.section_path else chunk.section_title,
                "original": chunk.text,
                "translation": translation,
                "issues": issues_text,
                "document_profile": self.document_profile.to_prompt_text(),
                "glossary": "\n".join([f"- {en}: {zh}" for en, zh in self.glossary.items()]),
            }),
            timeout=self.config.request_timeout,
        )

    async def translate_batch(
        self,
        text: str,
        progress_callback: Optional[Callable] = None,
        prepared_chunks: Optional[List[TextChunk]] = None,
    ) -> List[TranslationResult]:
        """
        批量翻译完整文本

        引擎只负责产出 TranslationResult 列表；最终如何落盘（单语/双语、
        是否格式化）由调用方使用 result_renderer 统一渲染，避免两套写文件
        逻辑互相覆盖。

        Args:
            text: 完整文本
            progress_callback: 进度回调
            prepared_chunks: 预先规划好的 chunk（可选）

        Returns:
            翻译结果列表（按 chunk_index 排序）
        """
        # 1. 文本分块
        chunks = prepared_chunks or self.plan_chunks(text)
        total = len(chunks)
        self.document_profile = await self.analyze_document(text, chunks)
        await self.cache.initialize()

        if progress_callback:
            await progress_callback({
                "event": "split_completed",
                "total_chunks": total
            })

        # 2. 准备任务列表（命中缓存的直接复用，未命中的并发翻译）
        tasks = []
        results: List[TranslationResult] = []
        for chunk in chunks:
            cache_entry = await self.cache.get(self._build_cache_key(chunk))
            if cache_entry:
                cached_result = TranslationResult(
                    chunk_index=chunk.index,
                    original=chunk.text,
                    translation=cache_entry.translation,
                    success=True,
                    retry_count=0,
                    duration=0.0,
                    chunk_id=chunk.chunk_id,
                    quality_report=cache_entry.quality_report,
                    repaired=cache_entry.repaired,
                    cached=True,
                )
                if progress_callback:
                    await progress_callback({
                        "chunk_index": chunk.index,
                        "chunk_id": chunk.chunk_id,
                        "status": "completed",
                        "translation": cache_entry.translation,
                        "duration": 0.0,
                        "quality_report": cache_entry.quality_report,
                        "repaired": cache_entry.repaired,
                        "cached": True,
                    })
                results.append(cached_result)
                continue

            tasks.append(self._process_one_chunk(chunk, progress_callback))

        # 3. 并发执行
        live_results = await asyncio.gather(*tasks)
        results.extend(live_results)

        return sorted(results, key=lambda r: r.chunk_index)

    async def _process_one_chunk(
        self,
        chunk: TextChunk,
        callback: Optional[Callable]
    ) -> TranslationResult:
        """单块处理(信号量控制)"""
        async with self.semaphore:
            return await self.translate_chunk(chunk, callback)
