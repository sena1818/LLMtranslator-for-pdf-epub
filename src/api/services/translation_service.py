"""
翻译任务管理服务
"""
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

from ..models.task import TranslationTask, TaskStatus, TaskProgress
from ..database.db import Database
from .glossary_service import GlossaryService

# 导入现有的翻译引擎（完全复用）
from ...core.translator import TranslationEngine
from ...converters.document_converter import DocumentConverter


class TranslationService:
    """翻译任务管理服务"""

    def __init__(self):
        self.db = Database()
        self.converter = DocumentConverter()
        self.glossary_service = GlossaryService()
        self.active_tasks = {}  # 运行中的任务

    async def create_task(
        self,
        file_content: bytes,
        filename: str,
        glossary_id: Optional[str] = None,
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
        await self.db.save_task(task)

        return task

    async def claim_next_pending_task(self) -> Optional[TranslationTask]:
        """认领一个待处理任务"""
        return await self.db.claim_next_pending_task()

    async def requeue_stale_tasks(self, stale_after_seconds: int = 900) -> int:
        """重新排队长时间未更新的 processing 任务"""
        return await self.db.requeue_stale_processing_tasks(stale_after_seconds)

    async def start_translation(self, task_id: str, already_claimed: bool = False):
        """
        启动翻译 (后台任务)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        task = await self.db.get_task(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        try:
            logger.info(f"🚀 开始翻译任务: {task.filename} (ID: {task_id})")
            
            if not already_claimed:
                # 兼容直接调用场景
                task.status = TaskStatus.PROCESSING
                task.updated_at = datetime.now()
                await self.db.update_task(task)

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
                        await self.db.update_task(task)
                        markdown_file = self.converter.convert(file_path, temp_dir)
                        logger.info(f"✅ 文档转换成功: {markdown_file}")
                except Exception as e:
                    logger.error(f"❌ 文档转换失败: {str(e)}")
                    raise RuntimeError(f"文档转换失败: {str(e)}")

                if markdown_file is None:
                    raise RuntimeError(f"文档转换失败: 未能生成 Markdown 文件")
            else:
                markdown_file = file_path

            # 3. 读取文本
            if not markdown_file.exists():
                raise RuntimeError(f"Markdown 文件不存在: {markdown_file}")

            task.updated_at = datetime.now()
            await self.db.update_task(task)

            with open(markdown_file, 'r', encoding='utf-8') as f:
                text = f.read()

            # 4. 加载术语表
            glossary = {}
            if task.glossary_id:
                logger.info(f"📚 加载术语表: {task.glossary_id}")
                glossary_data = await self.glossary_service.get_glossary(task.glossary_id)
                if glossary_data:
                    glossary = glossary_data.get("terms", {})

            # 5. 初始化翻译引擎
            engine = TranslationEngine(glossary=glossary)

            # 6. 文本分块
            chunks = engine.plan_chunks(text)
            task.progress.total = len(chunks)
            await self.db.update_task(task)
            logger.info(f"✂️ 文本已分块: {len(chunks)} chunks")

            # 7. 准备输出路径
            result_dir = Path("data/results")
            result_dir.mkdir(parents=True, exist_ok=True)
            output_path = result_dir / f"{task_id}.md"

            # 初始化输出文件
            with open(output_path, 'w', encoding='utf-8') as f:
                mode_text = "（双语对照）" if task.bilingual else ""
                f.write(f"# {task.filename} - 中文翻译{mode_text}\n\n")
                f.write(f"> 由 AI 自动翻译\n\n")

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
                    await self.db.update_task(task)

            # 9. 执行翻译 (支持双语对照模式)
            logger.info("🎬 开始调用 LLM 进行翻译...")
            results = await engine.translate_batch(
                text=text,
                output_path=output_path,
                progress_callback=progress_callback,
                bilingual=task.bilingual,
                prepared_chunks=chunks,
            )

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
            await self.db.update_task(task)
            logger.info(
                f"✅ 翻译任务结束: status={task.status.value}, "
                f"成功 {success_count} / 失败 {failed_count}, "
                f"修复 {sum(1 for result in results if getattr(result, 'repaired', False))}, "
                f"结果保存在: {output_path}"
            )

        except Exception as e:
            # 标记失败
            logger.error(f"❌ 任务失败: {str(e)}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now()
            await self.db.update_task(task)

    def _find_reusable_markdown(self, file_path: Path, temp_dir: Path) -> Optional[Path]:
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

    async def get_task(self, task_id: str) -> Optional[TranslationTask]:
        """获取任务"""
        return await self.db.get_task(task_id)

    async def list_tasks(self, skip: int = 0, limit: int = 20) -> Tuple[List[TranslationTask], int]:
        """获取任务列表"""
        return await self.db.list_tasks(skip, limit)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务及其所有相关文件"""
        import shutil

        task = await self.db.get_task(task_id)
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

        # 删除导出的 HTML 文件
        html_file = Path(f"data/results/{task_id}.html")
        if html_file.exists():
            html_file.unlink()

        # 删除临时目录 (PDF/EPUB 转换的中间文件)
        temp_dir = Path(f"data/temp/{task_id}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        # 从数据库删除
        return await self.db.delete_task(task_id)
