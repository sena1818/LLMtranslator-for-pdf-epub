import logging

from src.core.translator import TranslationEngine


def _engine() -> TranslationEngine:
    return TranslationEngine.__new__(TranslationEngine)


def test_intentional_repetition_is_preserved():
    engine = _engine()
    # 刻意的排比/咒语式重复（6 次）不应被折叠
    text = "走了走了走了走了走了走了"
    assert engine._remove_repetitions(text) == text


def test_runaway_loop_is_collapsed():
    engine = _engine()
    text = "循环" * 30
    collapsed = engine._remove_repetitions(text)
    # 折叠到最小重复单元，长度从 60 字骤降；不必精确到单个词
    assert len(collapsed) < 12


def test_runaway_phrase_loop_collapsed_and_logged(caplog):
    engine = _engine()
    text = "the same phrase " * 20
    with caplog.at_level(logging.WARNING):
        collapsed = engine._remove_repetitions(text)
    assert len(collapsed) < len(text)
    assert any("LLM 循环重复" in record.message for record in caplog.records)


def test_no_repetition_no_log(caplog):
    engine = _engine()
    text = "一段正常的中文文本，没有任何异常重复。"
    with caplog.at_level(logging.WARNING):
        assert engine._remove_repetitions(text) == text
    assert not caplog.records


def test_clean_output_still_strips_boilerplate():
    engine = _engine()
    assert engine.clean_output("Here is the translation: 正文内容") == "正文内容"
    assert engine.clean_output("正文内容（注：无关说明）") == "正文内容"
    assert engine.clean_output("```markdown\n正文内容\n```") == "正文内容"


def test_excess_punctuation_capped():
    engine = _engine()
    assert engine._remove_repetitions("结束。。。。。。。。") == "结束。。。"
