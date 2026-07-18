"""
术语表按块筛选

只把当前块（正文 + 上文语境）中实际出现的术语注入 prompt 与缓存键，
避免整表注入稀释模型注意力、浪费 token，也让「向术语表新增无关术语」
不再使全书缓存失效。匹配口径与 validator._check_glossary 保持一致：
英文术语键大小写无关的子串匹配。
"""
from __future__ import annotations


def select_relevant_glossary(
    glossary: dict[str, str],
    *texts: str,
) -> dict[str, str]:
    """返回 glossary 中英文术语出现在任一 text 内的子集，保持原插入顺序。

    Args:
        glossary: 完整术语表（英文术语 -> 中文译名）
        texts: 参与匹配的文本片段（如块正文、上文语境）

    Returns:
        过滤后的术语表；无术语或无文本时返回空 dict。
    """
    if not glossary:
        return {}
    haystack = "\n".join(text for text in texts if text).lower()
    if not haystack:
        return {}
    return {
        en: zh
        for en, zh in glossary.items()
        if en.lower() in haystack
    }
