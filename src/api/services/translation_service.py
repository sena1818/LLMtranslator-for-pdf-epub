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
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.core.translator import TranslationEngine
from src.converters.document_converter import DocumentConverter


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

    async def start_translation(self, task_id: str):
        """
        启动翻译 (后台任务)

        核心流程:
        1. 文档转换 (PDF/EPUB → Markdown)
        2. 加载术语表
        3. 调用 TranslationEngine.translate_batch
        4. 更新进度 (通过回调)
        5. 保存结果
        """
        task = await self.db.get_task(task_id)
        if not task:
            return

        try:
            # 更新状态为处理中
            task.status = TaskStatus.PROCESSING
            task.updated_at = datetime.now()
            await self.db.update_task(task)

            # 1. 获取文件路径
            file_path = Path(f"data/uploads/{task_id}_{task.filename}")

            # 2. 文档转换（如果需要）
            if file_path.suffix.lower() in ['.pdf', '.epub']:
                temp_dir = Path("data/temp") / task_id
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    markdown_file = self.converter.convert(file_path, temp_dir)
                except Exception as e:
                    raise RuntimeError(f"文档转换失败: {str(e)}")

                if markdown_file is None:
                    raise RuntimeError(f"文档转换失败: 未能生成 Markdown 文件")
            else:
                markdown_file = file_path

            # 3. 读取文本
            if not markdown_file.exists():
                raise RuntimeError(f"Markdown 文件不存在: {markdown_file}")

            with open(markdown_file, 'r', encoding='utf-8') as f:
                text = f.read()

            # 4. 加载术语表
            glossary = {}
            if task.glossary_id:
                glossary_data = await self.glossary_service.get_glossary(task.glossary_id)
                if glossary_data:
                    glossary = glossary_data.get("terms", {})

            # 5. 初始化翻译引擎
            engine = TranslationEngine(glossary=glossary)

            # 6. 文本分块
            chunks = engine.split_text(text)
            task.progress.total = len(chunks)
            await self.db.update_task(task)

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
                if event.get("status") == "completed":
                    task.progress.current += 1
                    elapsed = asyncio.get_event_loop().time() - start_time
                    task.progress.elapsed = elapsed
                    task.progress.percentage = (task.progress.current / task.progress.total) * 100
                    task.progress.speed = (task.progress.current / elapsed) * 60 if elapsed > 0 else 0

                    # 更新数据库
                    await self.db.update_task(task)

            # 9. 执行翻译 (支持双语对照模式)
            results = await engine.translate_batch(
                text=text,
                output_path=output_path,
                progress_callback=progress_callback,
                bilingual=task.bilingual
            )

            # 10. 标记完成
            task.status = TaskStatus.COMPLETED
            task.result_url = f"/api/files/results/{task_id}"
            task.updated_at = datetime.now()
            await self.db.update_task(task)

        except Exception as e:
            # 标记失败
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now()
            await self.db.update_task(task)

    async def get_task(self, task_id: str) -> Optional[TranslationTask]:
        """获取任务"""
        return await self.db.get_task(task_id)

    async def list_tasks(self, skip: int = 0, limit: int = 20) -> Tuple[List[TranslationTask], int]:
        """获取任务列表"""
        return await self.db.list_tasks(skip, limit)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        task = await self.db.get_task(task_id)
        if not task or task.status == TaskStatus.PROCESSING:
            return False

        # 删除文件
        upload_file = Path(f"data/uploads/{task_id}_{task.filename}")
        if upload_file.exists():
            upload_file.unlink()

        result_file = Path(f"data/results/{task_id}.md")
        if result_file.exists():
            result_file.unlink()

        # 从数据库删除
        return await self.db.delete_task(task_id)
