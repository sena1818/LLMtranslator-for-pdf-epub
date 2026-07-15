"""
LLM-as-judge：用注入的裁判 Runnable 给译文打分。

裁判用异源强模型（Gemini），避免与 DeepSeek 选手同源的自我偏好。裁判本身是一个
LangChain Runnable，测试时注入假 Runnable（RunnableLambda 返回固定 JSON）即可验证
打分解析逻辑，不触网、不需密钥。
"""
from __future__ import annotations

import json
import logging
import re

from .models import DIMENSIONS, SCORE_MAX, SCORE_MIN, DimensionScores, EvalSample, JudgeVerdict

logger = logging.getLogger(__name__)


def _clamp(value: float) -> float:
    """把打分夹到量表区间内。"""
    return float(max(SCORE_MIN, min(SCORE_MAX, value)))


def parse_scores(raw: str) -> DimensionScores:
    """从裁判的原始输出中解析三维打分。

    宽容处理：允许 ```json 代码块包裹、允许 JSON 前后有解释文字；缺失维度回退到量表中点；
    完全无法解析出 JSON 对象时抛 ValueError，交由调用方记录为该样本的评测失败。
    """
    payload_text = raw.strip()
    if not payload_text.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", payload_text)
        if not match:
            raise ValueError(f"裁判输出中未找到 JSON 对象：{raw[:120]!r}")
        payload_text = match.group(0)

    try:
        data = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"裁判输出 JSON 解析失败：{exc}") from exc

    midpoint = (SCORE_MIN + SCORE_MAX) / 2
    values = {}
    for dimension in DIMENSIONS:
        raw_value = data.get(dimension)
        if raw_value is None:
            logger.warning("裁判输出缺少维度 %s，回退到中点分 %s。", dimension, midpoint)
            values[dimension] = midpoint
            continue
        try:
            values[dimension] = _clamp(float(raw_value))
        except (TypeError, ValueError):
            logger.warning("裁判维度 %s 的分值 %r 非法，回退到中点分。", dimension, raw_value)
            values[dimension] = midpoint

    return DimensionScores(**values)


def _extract_text(result) -> str:
    """把 Runnable 的返回归一化成文本（兼容 str 与带 .content 的消息对象）。"""
    if isinstance(result, str):
        return result
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # 某些多模态消息把 content 存成分段列表
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(result)


class TranslationJudge:
    """封装裁判 Prompt 构造、调用与打分解析。"""

    def __init__(self, judge_runnable, prompt_template: str):
        """
        Args:
            judge_runnable: 符合 Runnable 协议的裁判模型（真实为 Gemini，测试注入假 Runnable）
            prompt_template: 裁判 Prompt 模板，占位符 {source}/{translation}/{glossary}
        """
        self.judge_runnable = judge_runnable
        self.prompt_template = prompt_template

    def build_prompt(self, sample: EvalSample, translation: str) -> str:
        glossary_text = "\n".join(f"- {en}: {zh}" for en, zh in sample.glossary.items()) or "（无术语表）"
        return self.prompt_template.format(
            source=sample.source_text,
            translation=translation,
            glossary=glossary_text,
        )

    async def score(self, sample: EvalSample, translation: str) -> JudgeVerdict:
        prompt = self.build_prompt(sample, translation)
        result = await self.judge_runnable.ainvoke(prompt)
        raw = _extract_text(result)
        scores = parse_scores(raw)
        rationale = self._extract_rationale(raw)
        return JudgeVerdict(sample_id=sample.id, scores=scores, rationale=rationale)

    @staticmethod
    def _extract_rationale(raw: str) -> str:
        try:
            match = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(match.group(0)) if match else {}
        except (json.JSONDecodeError, AttributeError):
            return ""
        return str(data.get("rationale", "")).strip()
