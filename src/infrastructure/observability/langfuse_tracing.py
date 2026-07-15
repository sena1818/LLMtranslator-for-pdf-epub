"""
Langfuse 可观测接入 + 本地 token 采集

两件事：

1. ``build_langfuse_callbacks``：按配置开关与环境变量构造 Langfuse 的 LangChain 回调，
   经 LangChain 回调链自动追踪每个 Agent（分析员/翻译员/审校员）的调用与逐块 token 消耗。
   缺 SDK、缺密钥或未开启时一律降级为空列表（无操作），生产与瘦测试环境都安全。

2. ``UsageMetadataCollector``：一个轻量 LangChain 回调，把每次 LLM 调用的 token 用量累加起来，
   让评测在没有 Langfuse 服务时也能拿到 token 数据；Langfuse 开启时两者并存、互不影响。

密钥从环境变量读取，不写入配置文件或代码：
``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` / ``LANGFUSE_HOST``（可选，默认云版）。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 瘦测试环境可能缺 langchain_core
    from langchain_core.callbacks import BaseCallbackHandler as _BaseCallbackHandler

    _HAS_CALLBACKS = True
except ImportError:  # pragma: no cover
    _BaseCallbackHandler = object  # type: ignore[assignment,misc]
    _HAS_CALLBACKS = False

_LANGFUSE_ENV_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


@dataclass(frozen=True)
class LangfuseSettings:
    """Langfuse 接入的生效配置。"""

    enabled: bool
    has_credentials: bool
    host: str | None

    @property
    def active(self) -> bool:
        """既开启又具备密钥，才真正接入。"""
        return self.enabled and self.has_credentials


def langfuse_settings(config) -> LangfuseSettings:
    """读取开关与环境变量，得出 Langfuse 是否应当接入。"""
    enabled = bool(getattr(config, "langfuse_enabled", False))
    has_credentials = all(os.getenv(key) for key in _LANGFUSE_ENV_KEYS)
    return LangfuseSettings(
        enabled=enabled,
        has_credentials=has_credentials,
        host=os.getenv("LANGFUSE_HOST"),
    )


def build_langfuse_callbacks(config) -> list[Any]:
    """构造 Langfuse 的 LangChain 回调处理器列表。

    返回空列表表示无操作：未开启、缺密钥、或 SDK 不可用时都走这条降级路径，
    调用方可无条件把结果拼进 ``callbacks``，不必自己判空。
    """
    settings = langfuse_settings(config)
    if not settings.enabled:
        return []
    if not settings.has_credentials:
        logger.warning(
            "observability.langfuse.enabled=true，但缺少 %s，Langfuse 追踪降级为无操作。",
            "/".join(_LANGFUSE_ENV_KEYS),
        )
        return []

    try:
        from langfuse.langchain import CallbackHandler
    except Exception as exc:  # pragma: no cover - 取决于是否安装 langfuse + langchain
        logger.warning("无法导入 Langfuse LangChain 集成，追踪降级为无操作：%s", exc)
        return []

    try:
        handler = CallbackHandler()
    except Exception as exc:  # pragma: no cover - 构造失败（如客户端初始化异常）
        logger.warning("Langfuse 回调构造失败，追踪降级为无操作：%s", exc)
        return []

    logger.info("Langfuse 追踪已接入（host=%s）。", settings.host or "cloud")
    return [handler]


@dataclass
class UsageSnapshot:
    """某次采集窗口内的累计 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count,
        }


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """从 LLMResult 中尽力提取 (prompt, completion, total) token 数。

    兼容两种来源：
    - LangChain 消息上的 ``usage_metadata``（input/output/total_tokens）；
    - ``llm_output.token_usage``（OpenAI 兼容端点的 prompt/completion/total_tokens）。
    """
    prompt = completion = total = 0

    llm_output = getattr(response, "llm_output", None) or {}
    token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if token_usage:
        prompt = int(token_usage.get("prompt_tokens", 0) or 0)
        completion = int(token_usage.get("completion_tokens", 0) or 0)
        total = int(token_usage.get("total_tokens", 0) or 0)

    if not total:
        for generation_list in getattr(response, "generations", []) or []:
            for generation in generation_list:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None)
                if not usage:
                    continue
                prompt += int(usage.get("input_tokens", 0) or 0)
                completion += int(usage.get("output_tokens", 0) or 0)
                total += int(usage.get("total_tokens", 0) or 0)

    if not total:
        total = prompt + completion
    return prompt, completion, total


class UsageMetadataCollector(_BaseCallbackHandler):
    """把每次 LLM 调用的 token 用量累加起来的 LangChain 回调。

    与 Langfuse 相互独立：即使不接入 Langfuse，评测也能靠它拿到 token 数据。
    """

    def __init__(self) -> None:
        self.snapshot = UsageSnapshot()

    def on_llm_end(self, response: Any, **_kwargs: Any) -> None:
        prompt, completion, total = _extract_usage(response)
        self.snapshot.prompt_tokens += prompt
        self.snapshot.completion_tokens += completion
        self.snapshot.total_tokens += total
        self.snapshot.call_count += 1

    def reset(self) -> None:
        self.snapshot = UsageSnapshot()
