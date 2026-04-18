"""
LLM 模型工厂
"""
from __future__ import annotations

try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI
except ImportError:  # pragma: no cover - 允许轻量测试环境导入
    class _ChatOpenAI:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError("langchain_openai 未安装，无法初始化聊天模型")


class ChatModelFactory:
    """统一创建项目所需的聊天模型。"""

    def __init__(self, config):
        self.config = config

    def create_translator(self):
        return _ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.translator_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url,
        )

    def create_checker(self):
        return _ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.checker_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url,
        )

    def create_analyst(self):
        return _ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.analyst_temperature,
            api_key=self.config.api_key,
            base_url=self.config.api_base_url,
        )
