"""
核心翻译引擎
重构自 scripts/async_translator.py
"""
import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path

from ..domain.models.translation_models import DocumentProfile, TranslationResult
from ..domain.rules.chunk_planning import ChunkPlanner, TextChunk
from ..infrastructure.cache.translation_cache import TranslationCache
from ..infrastructure.llm.chat_model_factory import ChatModelFactory
from ..infrastructure.llm.rate_limiter import RateLimiter
from ..pipelines.translate.batch_orchestrator import TranslationBatchOrchestrator
from ..pipelines.translate.document_analyzer import DocumentAnalyzer
from ..pipelines.translate.prompt_builder import TranslationPromptBuilder
from ..pipelines.translate.quality_pipeline import TranslationQualityPipeline
from ..pipelines.translate.translation_client import TranslationClient
from ..utils.config_loader import get_config
from .output_manager import OutputManager
from .validator import QualityReport, TranslationValidator

logger = logging.getLogger(__name__)


class TranslationEngine:
    """异步翻译引擎"""

    def __init__(
        self,
        glossary: dict[str, str] = None,
        model_factory=None,
        engine: str | None = None,
        cache: TranslationCache | None = None,
    ):
        """
        初始化翻译引擎

        Args:
            glossary: 术语表字典
            model_factory: 聊天模型工厂，默认真实 ChatModelFactory；测试可注入符合 Runnable 协议的假 LLM
            engine: 编排引擎（langgraph | native），默认取配置 multi_agent.engine
            cache: chunk 翻译缓存，默认指向 data/translation_cache.db；测试可注入隔离缓存
        """
        self.config = get_config()
        self.glossary = glossary or {}

        model_factory = model_factory or ChatModelFactory(self.config)
        self.llm_translator = model_factory.create_translator()
        self.llm_checker = model_factory.create_checker()
        self.llm_analyst = model_factory.create_analyst()

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
        self.cache = cache or TranslationCache(self.config.root_dir / "data" / "translation_cache.db")
        self.document_profile = DocumentProfile.empty()
        self.prompt_version = "v3"
        self.prompt_builder = TranslationPromptBuilder()
        self.document_analyzer = DocumentAnalyzer(
            llm_analyst=self.llm_analyst,
            config=self.config,
            prompt_builder=self.prompt_builder,
        )
        self.quality_pipeline = TranslationQualityPipeline(
            validator=self.validator,
            config=self.config,
            llm_checker=self.llm_checker,
            prompt_builder=self.prompt_builder,
            rate_limiter=self.rate_limiter,
            clean_output=self.clean_output,
            glossary=self.glossary,
        )
        self.translation_client = TranslationClient(
            llm_translator=self.llm_translator,
            config=self.config,
            prompt_builder=self.prompt_builder,
            rate_limiter=self.rate_limiter,
            clean_output=self.clean_output,
            glossary=self.glossary,
        )
        self.batch_orchestrator = TranslationBatchOrchestrator(
            cache=self.cache,
            build_cache_key=self._build_cache_key,
        )
        self.engine_name = (engine or self.config.engine or "native").lower()

    def plan_chunks(self, text: str) -> list[TextChunk]:
        """结构化切块"""
        return self.chunk_planner.plan(text)

    def split_text(self, text: str) -> list[str]:
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

    def build_prompt(self, chunk: TextChunk, document_profile: DocumentProfile | None = None):
        """
        构建翻译 Prompt

        Args:
            chunk: 待翻译文本块
            document_profile: 文档级分析信息

        Returns:
            Prompt 模板
        """
        return self.prompt_builder.build_translation_prompt(chunk, document_profile)

    async def analyze_document(
        self,
        text: str,
        chunks: list[TextChunk],
    ) -> DocumentProfile:
        """文档分析 agent：提炼整本文档的风格与术语上下文"""
        return await self.document_analyzer.analyze(text, chunks)

    def _parse_document_profile(self, raw: str) -> DocumentProfile:
        """解析文档分析 agent 返回的 JSON"""
        return DocumentAnalyzer.parse(raw, self.config)

    def _build_cache_key(self, chunk: TextChunk) -> str:
        """构造缓存键，避免不同模型/术语表之间串用"""
        glossary_payload = "\n".join(
            f"{en}:{zh}" for en, zh in sorted(self.glossary.items())
        )
        payload = "|".join(
            [
                self.prompt_version,
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
        progress_callback: Callable | None = None
    ) -> TranslationResult:
        """
        翻译单个文本块

        Args:
            chunk: 结构化文本块
            progress_callback: 进度回调函数

        Returns:
            翻译结果
        """
        try:
            translation, retry, duration = await self.translation_client.translate(
                chunk=chunk,
                document_profile=self.document_profile,
            )
            translation, quality_report, repaired = await self._run_quality_pipeline(
                chunk=chunk,
                translation=translation,
            )

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
                retry_count=self.config.get("api.translator.max_retries", 3),
                chunk_id=chunk.chunk_id,
                quality_report={"passed": False, "issue_count": 1, "issues": []},
            )

    async def _run_quality_pipeline(
        self,
        chunk: TextChunk,
        translation: str,
    ) -> tuple[str, QualityReport, bool]:
        """质量检查与选择性修复"""
        return await self.quality_pipeline.run(
            chunk=chunk,
            translation=translation,
            document_profile=self.document_profile,
        )

    async def _repair_translation(
        self,
        chunk: TextChunk,
        translation: str,
        report: QualityReport,
    ) -> str:
        """对高风险 chunk 触发一次修复"""
        return await self.quality_pipeline.repair(
            chunk=chunk,
            translation=translation,
            report=report,
            document_profile=self.document_profile,
        )

    async def translate_batch(
        self,
        text: str,
        output_path: Path,
        progress_callback: Callable | None = None,
        bilingual: bool = False,
        prepared_chunks: list[TextChunk] | None = None,
    ) -> list[TranslationResult]:
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
        chunks = prepared_chunks or self.plan_chunks(text)

        if getattr(self, "engine_name", "native") == "langgraph":
            raise NotImplementedError("langgraph 引擎尚未实现")

        # native：手写 asyncio 编排（分析员 → 并发 fan-out → 顺序写盘）
        await self._prepare_document(text, chunks, progress_callback)
        return await self.batch_orchestrator.run(
            chunks=chunks,
            output_path=output_path,
            bilingual=bilingual,
            progress_callback=progress_callback,
            process_chunk=self._process_one_chunk,
        )

    async def _prepare_document(
        self,
        text: str,
        chunks: list[TextChunk],
        progress_callback: Callable | None,
    ) -> None:
        """文档级准备：运行分析员、初始化缓存、上报分块完成事件。两引擎共用。"""
        if hasattr(self, "analyze_document"):
            self.document_profile = await self.analyze_document(text, chunks)
        else:
            self.document_profile = DocumentProfile.empty()
        await self.cache.initialize()

        if progress_callback:
            await progress_callback({
                "event": "split_completed",
                "total_chunks": len(chunks),
            })

    async def _process_one_chunk(
        self,
        chunk: TextChunk,
        output_manager: OutputManager,
        callback: Callable | None
    ) -> TranslationResult:
        """单块处理(信号量控制)"""
        async with self.semaphore:
            result = await self.translate_chunk(chunk, callback)

            # 写入输出管理器
            await output_manager.add_result(
                index=result.chunk_index,
                content=result.translation,
                success=result.success,
                original_text=result.original
            )

            return result
