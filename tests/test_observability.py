"""可观测性单元测试：Langfuse 降级路径与本地 token 采集。"""
from __future__ import annotations

import os
from types import SimpleNamespace

from src.infrastructure.observability import (
    UsageMetadataCollector,
    build_langfuse_callbacks,
    langfuse_settings,
)


class _Cfg:
    def __init__(self, enabled: bool):
        self.langfuse_enabled = enabled


def _clear_langfuse_env(monkeypatch):
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(key, raising=False)


def test_disabled_returns_no_callbacks(monkeypatch):
    _clear_langfuse_env(monkeypatch)
    assert build_langfuse_callbacks(_Cfg(enabled=False)) == []


def test_enabled_without_credentials_degrades_to_noop(monkeypatch):
    _clear_langfuse_env(monkeypatch)
    settings = langfuse_settings(_Cfg(enabled=True))
    assert settings.enabled is True
    assert settings.has_credentials is False
    assert settings.active is False
    # 开启但缺密钥：降级为空列表而非抛错
    assert build_langfuse_callbacks(_Cfg(enabled=True)) == []


def test_settings_active_requires_both(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    settings = langfuse_settings(_Cfg(enabled=True))
    assert settings.has_credentials is True
    assert settings.active is True
    # 关闭时即使有密钥也不接入
    assert langfuse_settings(_Cfg(enabled=False)).active is False
    assert os.getenv("LANGFUSE_PUBLIC_KEY") == "pk"


def test_usage_collector_reads_usage_metadata():
    collector = UsageMetadataCollector()
    message = SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14})
    response = SimpleNamespace(generations=[[SimpleNamespace(message=message)]], llm_output=None)
    collector.on_llm_end(response)
    assert collector.snapshot.total_tokens == 14
    assert collector.snapshot.prompt_tokens == 10
    assert collector.snapshot.completion_tokens == 4
    assert collector.snapshot.call_count == 1


def test_usage_collector_reads_openai_token_usage_and_accumulates():
    collector = UsageMetadataCollector()
    response = SimpleNamespace(
        generations=[],
        llm_output={"token_usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
    )
    collector.on_llm_end(response)
    collector.on_llm_end(response)
    assert collector.snapshot.total_tokens == 16
    assert collector.snapshot.call_count == 2
    collector.reset()
    assert collector.snapshot.total_tokens == 0
    assert collector.snapshot.call_count == 0
