"""
速率限制器 (Token Bucket 算法)
从 scripts/async_translator.py:84-110 提取
"""
import asyncio
import time


class RateLimiter:
    """
    Token Bucket 速率限制器

    用于控制 API 请求速率,防止触发限流
    """

    def __init__(self, rate: int, per: int = 60):
        """
        初始化速率限制器

        Args:
            rate: 每个时间窗口的请求数 (如 200)
            per: 时间窗口长度(秒) (如 60)
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """
        获取一个令牌

        如果令牌不足,会自动等待
        """
        async with self.lock:
            current = time.time()
            time_passed = current - self.last_check
            self.last_check = current

            # 根据流逝时间补充令牌
            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = self.rate

            # 令牌不足时等待
            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.per / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0
