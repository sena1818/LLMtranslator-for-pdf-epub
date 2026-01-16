"""
顺序输出管理器
从 scripts/async_translator.py:422-478 提取
解决异步并发导致的乱序输出问题
"""
import asyncio
import aiofiles
import time


class OutputManager:
    """
    输出管理器

    核心功能:
    - 缓冲异步完成的结果
    - 按索引顺序写入文件
    - 失败块写入占位符,不阻塞后续
    """

    def __init__(self, output_path: str, start_index: int = 0):
        """
        初始化输出管理器

        Args:
            output_path: 输出文件路径
            start_index: 起始索引(用于断点续传)
        """
        self.output_path = output_path
        self.buffer = {}  # {index: content}
        self.next_index = start_index
        self.lock = asyncio.Lock()
        self.written_count = 0

    async def add_result(
        self,
        index: int,
        content: str,
        success: bool,
        original_text: str = ""
    ):
        """
        添加翻译结果

        Args:
            index: 块索引
            content: 翻译内容
            success: 是否成功
            original_text: 原文(用于失败占位符)
        """
        async with self.lock:
            # 1. 构造写入内容
            if success:
                final_content = content
            else:
                # 失败时写入占位符
                final_content = (
                    f"\n\n> **[翻译失败 - Chunk {index}]**\n"
                    f"> *API 请求失败或超时,请根据以下原文手动补全:*\n\n"
                    f"```text\n{original_text[:500]}...\n```\n\n"
                )

            # 2. 存入缓冲区
            self.buffer[index] = final_content

            # 3. 尝试连续写入 (Flush Buffer)
            async with aiofiles.open(self.output_path, 'a', encoding='utf-8') as f:
                while self.next_index in self.buffer:
                    text_to_write = self.buffer[self.next_index]

                    await f.write(f"\n\n")
                    await f.write(text_to_write)
                    await f.write(f"\n\n")

                    # 清理内存
                    del self.buffer[self.next_index]
                    self.next_index += 1
                    self.written_count += 1

    @property
    def current_index(self) -> int:
        """当前应写入的索引"""
        return self.next_index

    @property
    def buffer_size(self) -> int:
        """缓冲区大小"""
        return len(self.buffer)
