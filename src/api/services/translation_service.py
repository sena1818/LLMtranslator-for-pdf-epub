"""
翻译任务管理服务
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from ...application.use_cases.run_translation_pipeline import RunTranslationPipeline
from ...converters.document_converter import DocumentConverter
from ...core.translator import TranslationEngine
from ...domain.models.task_models import TaskProgress, TaskStatus, TranslationTask
from ...infrastructure.persistence.task_repository import TaskRepository
from ...pipelines.postprocess.result_postprocess_pipeline import ResultPostprocessPipeline
from ..database.db import Database
from .glossary_service import GlossaryService


class TranslationService:
    """翻译任务管理服务"""

    def __init__(self):
        self.tasks = TaskRepository()
        self.converter = DocumentConverter()
        self.glossary_service = GlossaryService()
        self.postprocess_pipeline = ResultPostprocessPipeline()
        self.active_tasks = {}  # 运行中的任务

    @property
    def db(self) -> Database:
        """兼容旧调用：暴露底层 Database 实例。"""
        return self.tasks.db

    @db.setter
    def db(self, value: Database):
        """兼容测试/旧代码直接替换数据库实例。"""
        self.tasks = TaskRepository(value)

    async def create_task(
        self,
        file_content: bytes,
        filename: str,
        glossary_id: str | None = None,
        bilingual: bool = False
    ) -> TranslationTask:
        """创建翻译任务"""
        task_id = str(uuid.uuid4())

        # 保存上传文件
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / f"{task_id}_{filename}"
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 创建任务对象
        task = TranslationTask(
            task_id=task_id,
            filename=filename,
            status=TaskStatus.PENDING,
            glossary_id=glossary_id,
            bilingual=bilingual,
            progress=TaskProgress(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 保存到数据库
        await self.tasks.save(task)

        return task

    async def claim_next_pending_task(self) -> TranslationTask | None:
        """认领一个待处理任务"""
        return await self.tasks.claim_next_pending()

    async def requeue_stale_tasks(self, stale_after_seconds: int = 900) -> int:
        """重新排队长时间未更新的 processing 任务"""
        return await self.tasks.requeue_stale_processing(stale_after_seconds)

    async def start_translation(self, task_id: str, already_claimed: bool = False):
        """
        启动翻译 (后台任务)
        """
        import logging
        logger = logging.getLogger(__name__)

        task = await self.tasks.get(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        try:
            logger.info(f"🚀 开始翻译任务: {task.filename} (ID: {task_id})")

            if not already_claimed:
                # 兼容直接调用场景
                task.status = TaskStatus.PROCESSING
                task.updated_at = datetime.now()
                await self.tasks.update(task)

            # 1. 获取文件路径
            file_path = Path(f"data/uploads/{task_id}_{task.filename}")
            temp_dir = Path("data/temp") / task_id

            # 2. 文档转换（如果需要）
            if file_path.suffix.lower() in ['.pdf', '.epub', '.mobi']:
                logger.info(f"📄 开始转换文档: {file_path.name}")
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    markdown_file = self._find_reusable_markdown(file_path, temp_dir)
                    if markdown_file:
                        logger.info(f"♻️ 复用已转换 Markdown: {markdown_file}")
                    else:
                        task.updated_at = datetime.now()
                        await self.tasks.update(task)
                        markdown_file = self.converter.convert(file_path, temp_dir)
                        logger.info(f"✅ 文档转换成功: {markdown_file}")
                except Exception as e:
                    logger.error(f"❌ 文档转换失败: {str(e)}")
                    raise RuntimeError(f"文档转换失败: {str(e)}") from e

                if markdown_file is None:
                    raise RuntimeError("文档转换失败: 未能生成 Markdown 文件")
            else:
                markdown_file = file_path

            # 3. 读取文本
            if not markdown_file.exists():
                raise RuntimeError(f"Markdown 文件不存在: {markdown_file}")

            task.updated_at = datetime.now()
            await self.tasks.update(task)

            with open(markdown_file, encoding='utf-8') as f:
                text = f.read()

            # 4. 加载术语表
            glossary = {}
            if task.glossary_id:
                logger.info(f"📚 加载术语表: {task.glossary_id}")
                glossary_data = await self.glossary_service.get_glossary(task.glossary_id)
                if glossary_data:
                    glossary = glossary_data.get("terms", {})

            # 5. 初始化翻译引擎
            translation_use_case = RunTranslationPipeline(
                glossary=glossary,
                engine_cls=TranslationEngine,
            )

            # 6. 文本分块
            chunks = translation_use_case.plan_chunks(text)
            task.progress.current = 0
            task.progress.total = len(chunks)
            task.progress.percentage = 0.0
            task.progress.speed = 0.0
            task.progress.elapsed = 0.0
            await self.tasks.update(task)
            logger.info(f"✂️ 文本已分块: {len(chunks)} chunks")

            # 7. 准备输出路径
            result_dir = Path("data/results")
            result_dir.mkdir(parents=True, exist_ok=True)
            mono_output_path = result_dir / f"{task_id}.md"
            bilingual_output_path = result_dir / f"{task_id}.bilingual.md"
            engine_output_path = bilingual_output_path if task.bilingual else mono_output_path

            self._initialize_output_file(engine_output_path, task.filename, task.bilingual)

            # 8. 定义进度回调
            start_time = asyncio.get_event_loop().time()

            async def progress_callback(event: dict):
                if event.get("status") in {"completed", "failed"}:
                    task.progress.current += 1
                    elapsed = asyncio.get_event_loop().time() - start_time
                    task.progress.elapsed = elapsed
                    task.progress.percentage = (
                        (task.progress.current / task.progress.total) * 100
                        if task.progress.total > 0 else 100.0
                    )
                    task.progress.speed = (task.progress.current / elapsed) * 60 if elapsed > 0 else 0

                    # 只有当进度整除 5 或完成时才打印详细日志，避免刷屏
                    if task.progress.current % 5 == 0 or task.progress.current == task.progress.total:
                        logger.info(f"⏳ 进度: {task.progress.current}/{task.progress.total} ({task.progress.percentage:.1f}%)")

                    if event.get("status") == "failed":
                        logger.error(f"❌ Chunk 翻译失败: {event.get('error')}")

                    # 更新数据库
                    await self.tasks.update(task)

            # 9. 执行翻译 (支持双语对照模式)
            logger.info("🎬 开始调用 LLM 进行翻译...")
            pipeline_output = await translation_use_case.execute(
                text=text,
                output_path=engine_output_path,
                progress_callback=progress_callback,
                bilingual=task.bilingual,
                prepared_chunks=chunks,
            )
            results = pipeline_output.results

            self._write_result_markdown(
                output_path=mono_output_path,
                filename=task.filename,
                results=results,
                bilingual=False,
            )

            if task.bilingual:
                self._write_result_markdown(
                    output_path=bilingual_output_path,
                    filename=task.filename,
                    results=results,
                    bilingual=True,
                )

            asset_sources = []
            if temp_dir.exists():
                asset_sources.extend([
                    temp_dir,
                    temp_dir / "images",
                    temp_dir / "images" / "images",
                ])
            copied_assets = self.postprocess_pipeline.sync_assets(
                markdown_paths=[
                    mono_output_path,
                    bilingual_output_path if task.bilingual else None,
                ],
                asset_sources=asset_sources,
                task_id=task_id,
            )

            if copied_assets:
                logger.info("🖼️ 已同步 %s 张图片到结果目录", len(copied_assets))

            # 10. 根据成功率标记任务状态
            failed_results = [result for result in results if not result.success]
            failed_count = len(failed_results)
            success_count = len(results) - failed_count

            if failed_count == 0:
                task.status = TaskStatus.COMPLETED
                task.result_url = f"/api/files/results/{task_id}"
                task.error = None
            elif success_count == 0:
                task.status = TaskStatus.FAILED
                task.result_url = None
                task.error = f"全部 {failed_count} 个文本块翻译失败"
            else:
                preview = ", ".join(str(result.chunk_index) for result in failed_results[:10])
                if failed_count > 10:
                    preview = f"{preview} ..."
                task.status = TaskStatus.PARTIAL_SUCCESS
                task.result_url = f"/api/files/results/{task_id}"
                task.error = (
                    f"{failed_count}/{len(results)} 个文本块翻译失败"
                    f"；失败块索引: {preview}"
                )

            task.updated_at = datetime.now()
            await self.tasks.update(task)
            logger.info(
                f"✅ 翻译任务结束: status={task.status.value}, "
                f"成功 {success_count} / 失败 {failed_count}, "
                f"修复 {sum(1 for result in results if getattr(result, 'repaired', False))}, "
                f"结果保存在: {mono_output_path}"
            )

        except Exception as e:
            # 标记失败
            logger.error(f"❌ 任务失败: {str(e)}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now()
            await self.tasks.update(task)

    def _find_reusable_markdown(self, file_path: Path, temp_dir: Path) -> Path | None:
        """查找可复用的转换结果，避免中断后重复转换"""
        if file_path.suffix.lower() not in {".epub", ".mobi"}:
            return None

        expected = temp_dir / f"{file_path.stem}.md"
        if expected.exists() and expected.stat().st_size > 0:
            return expected

        md_files = sorted(
            candidate for candidate in temp_dir.rglob("*.md")
            if candidate.is_file() and candidate.stat().st_size > 0
        )
        return md_files[0] if md_files else None

    def _initialize_output_file(self, output_path: Path, filename: str, bilingual: bool) -> None:
        """初始化结果文件头"""
        with open(output_path, 'w', encoding='utf-8') as f:
            mode_text = "（双语对照）" if bilingual else ""
            f.write(f"# {filename} - 中文翻译{mode_text}\n\n")
            f.write("> 由 AI 自动翻译\n\n")

    def _write_result_markdown(
        self,
        output_path: Path,
        filename: str,
        results: list,
        bilingual: bool,
    ) -> None:
        """根据翻译结果渲染最终 Markdown，统一单语/双语产物格式。"""
        self._initialize_output_file(output_path, filename, bilingual)

        with open(output_path, 'a', encoding='utf-8') as f:
            for result in sorted(results, key=lambda item: item.chunk_index):
                if result.success:
                    if bilingual:
                        original_lines = result.original.strip().split('\n')
                        quoted_original = '\n'.join(f'> {line}' for line in original_lines)
                        content = f"{quoted_original}\n\n{result.translation}\n\n---"
                    else:
                        content = result.translation
                else:
                    content = (
                        f"\n\n> **[翻译失败 - Chunk {result.chunk_index}]**\n"
                        f"> *API 请求失败或超时,请根据以下原文手动补全:*\n\n"
                        f"```text\n{result.original[:500]}...\n```\n\n"
                    )

                f.write("\n\n")
                f.write(content)
                f.write("\n\n")

    async def get_task(self, task_id: str) -> TranslationTask | None:
        """获取任务"""
        return await self.tasks.get(task_id)

    async def list_tasks(self, skip: int = 0, limit: int = 20) -> tuple[list[TranslationTask], int]:
        """获取任务列表"""
        return await self.tasks.list(skip, limit)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务及其所有相关文件"""
        import shutil

        task = await self.tasks.get(task_id)
        if not task or task.status == TaskStatus.PROCESSING:
            return False

        # 删除上传文件
        upload_file = Path(f"data/uploads/{task_id}_{task.filename}")
        if upload_file.exists():
            upload_file.unlink()

        # 删除结果文件 (MD)
        result_file = Path(f"data/results/{task_id}.md")
        if result_file.exists():
            result_file.unlink()

        bilingual_result_file = Path(f"data/results/{task_id}.bilingual.md")
        if bilingual_result_file.exists():
            bilingual_result_file.unlink()

        # 删除导出的 HTML 文件
        html_file = Path(f"data/results/{task_id}.html")
        if html_file.exists():
            html_file.unlink()

        downloads_dir = Path("data/results/downloads")
        if downloads_dir.exists():
            for bundle_path in downloads_dir.glob(f"{task_id}.*.zip"):
                bundle_path.unlink()

        assets_dir = Path(f"data/results/assets/{task_id}")
        if assets_dir.exists():
            shutil.rmtree(assets_dir)

        # 删除临时目录 (PDF/EPUB 转换的中间文件)
        temp_dir = Path(f"data/temp/{task_id}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        # 从数据库删除
        return await self.tasks.delete(task_id)
