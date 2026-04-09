"""
配置加载器
从 YAML 文件加载配置,并支持环境变量覆盖
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径,默认为 config/config.yaml
        """
        # 加载环境变量
        load_dotenv()

        # 确定项目根目录
        self.root_dir = Path(__file__).parent.parent.parent

        # 加载 YAML 配置
        if config_path is None:
            config_path = self.root_dir / "config" / "config.yaml"

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值,支持嵌套路径

        Args:
            key_path: 配置路径,如 "api.model" 或 "concurrency.max_concurrent_requests"
            default: 默认值

        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_path(self, path_key: str) -> Path:
        """
        获取路径配置(自动转换为绝对路径)

        Args:
            path_key: 路径键名,如 "input", "output", "glossaries"

        Returns:
            绝对路径
        """
        relative_path = self.config['paths'].get(path_key)
        if relative_path:
            return self.root_dir / relative_path
        return self.root_dir

    @property
    def artifact_rules_path(self) -> Path:
        """源文件残留规则库路径"""
        relative_path = self.get("paths.artifact_rules", "config/artifact_rules.yaml")
        return self.root_dir / relative_path

    @property
    def api_key(self) -> str:
        """获取 API Key (优先从环境变量)"""
        return os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")

    @property
    def api_base_url(self) -> str:
        """获取 API 基础 URL"""
        return self.get("api.base_url")

    @property
    def model_name(self) -> str:
        """获取模型名称"""
        return self.get("api.model")

    @property
    def translator_temperature(self) -> float:
        """获取翻译温度"""
        return self.get("api.translator.temperature", 0.3)

    @property
    def checker_temperature(self) -> float:
        """获取质检温度"""
        return self.get("api.checker.temperature", 0.1)

    @property
    def max_concurrent(self) -> int:
        """获取最大并发数"""
        return self.get("concurrency.max_concurrent_requests", 10)

    @property
    def batch_size(self) -> int:
        """获取批次大小"""
        return self.get("concurrency.batch_size", 5)

    @property
    def rate_limit(self) -> int:
        """获取速率限制 (每分钟请求数)"""
        return self.get("concurrency.rate_limit_per_minute", 200)

    @property
    def chunk_size(self) -> int:
        """获取文本块大小"""
        return self.get("text_splitting.chunk_size", 3600)

    @property
    def target_chunk_size(self) -> int:
        """理想目标块大小"""
        return self.get("text_splitting.target_chunk_size", 3200)

    @property
    def min_chunk_size(self) -> int:
        """尽量避免生成过小块"""
        return self.get("text_splitting.min_chunk_size", 1200)

    @property
    def chunk_overlap(self) -> int:
        """获取上下文重叠窗口"""
        return self.get("text_splitting.chunk_overlap", 0)

    @property
    def context_window(self) -> int:
        """获取传给模型的上一块上下文窗口"""
        return self.get("text_splitting.context_window", 1400)

    @property
    def enable_qa_check(self) -> bool:
        """是否启用质量检查"""
        return self.get("quality.enable_qa_check", True)

    @property
    def max_fix_attempts(self) -> int:
        """获取最大修复次数"""
        return self.get("quality.max_fix_attempts", 1)

    @property
    def untranslated_word_span(self) -> int:
        """未翻译英文阈值"""
        return self.get("quality.untranslated_word_span", 12)

    @property
    def max_glossary_checks(self) -> int:
        """每块最多检查多少术语"""
        return self.get("quality.max_glossary_checks", 25)

    @property
    def worker_poll_interval(self) -> float:
        """worker 轮询间隔"""
        return float(self.get("worker.poll_interval_seconds", 2.0))

    @property
    def worker_stale_after(self) -> int:
        """多久判定 processing 任务为陈旧"""
        return int(self.get("worker.stale_after_seconds", 900))

    @property
    def inline_worker_enabled(self) -> bool:
        """是否默认启用 API 内联 worker"""
        return bool(self.get("worker.inline_enabled", True))

    @property
    def worker_max_parallel_tasks(self) -> int:
        """单个 worker 进程允许并发处理的任务数"""
        return int(self.get("worker.max_parallel_tasks", 1))

    @property
    def worker_processes(self) -> int:
        """默认启动多少个 worker 进程"""
        return int(self.get("worker.processes", 1))

    @property
    def server_reload(self) -> bool:
        """是否启用开发热重载"""
        return bool(self.get("server.reload", False))

    @property
    def server_port(self) -> int:
        """Web 服务端口"""
        return int(self.get("server.port", 8000))

    @property
    def server_reload_dirs(self) -> list[str]:
        """热重载监听目录"""
        return list(self.get("server.reload_dirs", ["src", "frontend"]))

    @property
    def multi_agent_enabled(self) -> bool:
        """是否启用三角色多 agent 流水线"""
        return bool(self.get("multi_agent.enabled", True))

    @property
    def analyst_temperature(self) -> float:
        """文档分析 agent 温度"""
        return float(self.get("multi_agent.analyst_temperature", 0.1))

    @property
    def analyst_max_chars(self) -> int:
        """文档分析最大采样字符数"""
        return int(self.get("multi_agent.analyst_max_chars", 12000))

    @property
    def analyst_max_sections(self) -> int:
        """文档分析最大章节数"""
        return int(self.get("multi_agent.analyst_max_sections", 12))

    @property
    def analyst_max_term_hints(self) -> int:
        """文档分析最多返回多少术语提示"""
        return int(self.get("multi_agent.analyst_max_term_hints", 12))


# 全局配置实例
_config = None

def get_config(config_path: str = None) -> Config:
    """
    获取全局配置实例 (单例模式)

    Args:
        config_path: 配置文件路径

    Returns:
        Config 实例
    """
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config
